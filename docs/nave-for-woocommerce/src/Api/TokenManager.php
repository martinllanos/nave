<?php
/**
 * Token Manager.
 *
 * Obtiene y cachea el access token de Nave usando WordPress transients.
 * SEGURIDAD: El token se cifra con AES-256-CBC antes de guardarse en DB.
 * La clave de cifrado se deriva de NONCE_KEY (definida en wp-config.php,
 * nunca almacenada en base de datos).
 *
 * @package NaveWC\Api
 */

declare( strict_types=1 );

namespace NaveWC\Api;

defined( 'ABSPATH' ) || exit;

use NaveWC\Gateway\NaveGateway;

final class TokenManager {

    private const TRANSIENT_PREFIX = 'nave_wc_token_';
    private const AUTH_URL_SANDBOX = 'https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2ms';
    private const AUTH_URL_PROD    = 'https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate';
    private const AUDIENCE         = 'https://naranja.com/ranty/merchants/api';
    private const CIPHER           = 'aes-256-cbc';

    private NaveGateway $gateway;

    public function __construct( NaveGateway $gateway ) {
        $this->gateway = $gateway;
    }

    // ── API pública ───────────────────────────────────────────────────────────

    /**
     * Retorna un access token válido (desde caché descifrado, o nuevo).
     *
     * @throws \RuntimeException
     */
    public function get_token(): string {
        $cache_key = $this->cache_key();
        $cached    = get_transient( $cache_key );

        if ( $cached && is_string( $cached ) ) {
            $decrypted = $this->decrypt( $cached );
            if ( $decrypted ) {
                $this->log( 'Token obtenido desde cache (descifrado OK).' );
                return $decrypted;
            }
            // Descifrado falló (ej. rotación de NONCE_KEY) → pedir token nuevo.
            $this->log( 'Token en cache no pudo descifrarse. Solicitando nuevo.', 'warning' );
            delete_transient( $cache_key );
        }

        return $this->fetch_new_token( $cache_key );
    }

    /**
     * Fuerza un nuevo token (invalida caché).
     *
     * @throws \RuntimeException
     */
    public function refresh_token(): string {
        delete_transient( $this->cache_key() );
        return $this->fetch_new_token( $this->cache_key() );
    }

    // ── Internals ─────────────────────────────────────────────────────────────

    private function fetch_new_token( string $cache_key ): string {
        $url  = 'production' === $this->gateway->get_environment()
            ? self::AUTH_URL_PROD
            : self::AUTH_URL_SANDBOX;

        $body = wp_json_encode( [
            'client_id'     => $this->gateway->get_client_id(),
            'client_secret' => $this->gateway->get_client_secret(),
            'audience'      => self::AUDIENCE,
        ] );

        $this->log( 'Solicitando nuevo access token.' );

        $response = wp_remote_post( $url, [
            'headers'     => [ 'Content-Type' => 'application/json' ],
            'body'        => $body,
            'timeout'     => 30,
            'redirection' => 5,
            'sslverify'   => true, // Seguridad: Mitiga ataques MitM
        ] );

        if ( is_wp_error( $response ) ) {
            throw new \RuntimeException( 'No se pudo conectar al servidor de autenticación de Nave.' );
        }

        $status_code = wp_remote_retrieve_response_code( $response );
        $raw_body    = wp_remote_retrieve_body( $response );
        $data        = json_decode( $raw_body, true );

        if ( $status_code !== 200 || empty( $data['access_token'] ) ) {
            $this->log( 'Respuesta inesperada al obtener token. Status: ' . absint( $status_code ), 'error' );
            throw new \RuntimeException( 'No se pudo obtener un access token válido de Nave.' );
        }

        $token      = (string) $data['access_token'];
        $expires_in = isset( $data['expires_in'] ) ? (int) $data['expires_in'] : 3600;
        $ttl        = max( $expires_in - 60, 60 );

        // Cifrar antes de persistir en wp_options.
        $encrypted = $this->encrypt( $token );
        set_transient( $cache_key, $encrypted, $ttl );
        $this->log( 'Nuevo token cifrado y cacheado por ' . $ttl . ' segundos.' );

        return $token;
    }

    // ── Cifrado AES-256-CBC ───────────────────────────────────────────────────

    /**
     * Deriva una clave de 32 bytes a partir de NONCE_KEY de wp-config.php.
     * NONCE_KEY es única por instalación y NUNCA se guarda en la DB.
     */
    private function derive_key(): string {
        // Usa wp_salt('nonce') que genera o recupera sales únicas si NONCE_KEY no existe.
        $base = defined( 'NONCE_KEY' ) ? NONCE_KEY : wp_salt( 'nonce' );
        return hash( 'sha256', 'nave_token_enc_v2_' . $base, true ); // 32 bytes raw
    }

    /**
     * Cifra el plaintext con AES-256-CBC y devuelve base64( iv || ciphertext ).
     */
    private function encrypt( string $plaintext ): string {
        if ( ! function_exists( 'openssl_encrypt' ) ) {
            return $plaintext; // Fallback si OpenSSL no disponible.
        }

        $iv_len     = openssl_cipher_iv_length( self::CIPHER );
        $iv         = random_bytes( $iv_len );
        $ciphertext = openssl_encrypt( $plaintext, self::CIPHER, $this->derive_key(), OPENSSL_RAW_DATA, $iv );

        if ( false === $ciphertext ) {
            $this->log( 'Error al cifrar token. Se guarda en texto plano como fallback.', 'warning' );
            return $plaintext;
        }

        return base64_encode( $iv . $ciphertext );
    }

    /**
     * Descifra un valor producido por encrypt().
     * Retorna string vacío si falla (token corrupto o clave cambiada).
     */
    private function decrypt( string $encrypted ): string {
        if ( ! function_exists( 'openssl_decrypt' ) ) {
            return $encrypted; // Fallback si OpenSSL no disponible.
        }

        $decoded = base64_decode( $encrypted, true );
        if ( false === $decoded ) {
            return '';
        }

        $iv_len = openssl_cipher_iv_length( self::CIPHER );
        if ( strlen( $decoded ) <= $iv_len ) {
            return ''; // Dato corrupto o token plano antiguo.
        }

        $iv         = substr( $decoded, 0, $iv_len );
        $ciphertext = substr( $decoded, $iv_len );
        $plaintext  = openssl_decrypt( $ciphertext, self::CIPHER, $this->derive_key(), OPENSSL_RAW_DATA, $iv );

        return ( false !== $plaintext ) ? $plaintext : '';
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private function cache_key(): string {
        return self::TRANSIENT_PREFIX . md5( $this->gateway->get_client_id() . $this->gateway->get_environment() );
    }

    private function log( string $message, string $level = 'debug' ): void {
        if ( 'yes' !== $this->gateway->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[TokenManager] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
