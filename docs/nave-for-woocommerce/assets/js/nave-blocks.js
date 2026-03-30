/**
 * Nave for WooCommerce — Block Checkout Integration
 */
( function( wc, wp ) {
    'use strict';

    var registerPaymentMethod = wc.wcBlocksRegistry.registerPaymentMethod;
    var getSetting            = wc.wcSettings.getSetting;
    var createElement         = wp.element.createElement;

    var naveData  = getSetting( 'nave_data', {} );
    var isSandbox = naveData.is_sandbox  || false;
    var logoUrl   = naveData.icon_url    || '';
    var cardsUrl  = naveData.cards_url   || '';
    var title     = naveData.title       || 'Pagá con tarjetas, MODO o QR';
    var description = naveData.description || '';

    var cardNames = [ 'visa', 'mastercard', 'amex', 'cabal', 'modo', 'qr' ];

    /* ── Label: logos de tarjetas al lado del radio ────── */
    var NaveLabel = function() {
        var children = [ title ];

        if ( cardsUrl ) {
            cardNames.forEach( function( card ) {
                children.push(
                    createElement( 'img', {
                        key:   card,
                        src:   cardsUrl + card + '.svg',
                        alt:   card.toUpperCase(),
                        style: { height: '20px', width: 'auto', verticalAlign: 'middle', marginLeft: '4px', borderRadius: '3px', display: 'inline-block' }
                    } )
                );
            } );
        }

        return createElement( 'span', { style: { display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '2px' } }, ...children );
    };

    /* ── Content: expandido al seleccionar ─────────────── */
    var NaveContent = function() {
        return createElement(
            'div',
            null,

            createElement( 'style', {
                dangerouslySetInnerHTML: { __html: [
                    '.nave-block-content{padding:8px 0 2px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}',
                    '.nave-block-text{font-size:13.5px;color:#4B5563;line-height:1.5;margin:0 0 8px;}',
                    '.nave-redirect-notice{display:flex;align-items:center;gap:12px;background:#F3F4F6;border:1px solid #E5E7EB;border-radius:10px;padding:12px 16px;margin-top:4px;}',
                    '.nave-redirect-logo{height:18px;width:auto;flex-shrink:0;display:block;}',
                    '.nave-redirect-text{flex:1;display:flex;flex-direction:column;gap:2px;}',
                    '.nave-redirect-title{font-size:13px;font-weight:700;color:#1A1A1A;line-height:1.3;}',
                    '.nave-redirect-desc{font-size:12px;color:#6B7280;line-height:1.4;}',
                    '.nave-sandbox-pill{display:inline-flex;align-items:center;gap:5px;background:#fff8e6;border:1px solid #f59e0b;border-radius:20px;color:#92400e;font-size:11px;font-weight:700;padding:3px 10px;margin-top:10px;text-transform:uppercase;letter-spacing:.04em;}',
                    '.nave-sandbox-dot{width:6px;height:6px;background:#f59e0b;border-radius:50%;display:inline-block;animation:nave-pulse 1.5s ease-in-out infinite;}',
                    '@keyframes nave-pulse{0%,100%{opacity:1}50%{opacity:.3}}'
                ].join('') }
            } ),

            createElement(
                'div',
                { className: 'nave-block-content' },

                // Descripción
                description && createElement( 'p', { className: 'nave-block-text' }, description ),

                // Cartel redirección con logo Nave
                createElement(
                    'div',
                    { className: 'nave-redirect-notice' },
                    logoUrl && createElement( 'img', { src: logoUrl, alt: 'Nave', className: 'nave-redirect-logo' } ),
                    createElement(
                        'div',
                        { className: 'nave-redirect-text' },
                        createElement( 'span', { className: 'nave-redirect-title' }, 'Ser\u00e1s redirigido a Nave' ),
                        createElement( 'span', { className: 'nave-redirect-desc' },  'Complet\u00e1 el pago de forma segura en la plataforma de Nave.' )
                    ),
                    createElement(
                        'svg',
                        { width: '16', height: '16', viewBox: '0 0 16 16', fill: 'none', style: { color: '#6B7280', flexShrink: '0' } },
                        createElement( 'path', { d: 'M3 8H13M13 8L9 4M13 8L9 12', stroke: 'currentColor', strokeWidth: '1.5', strokeLinecap: 'round', strokeLinejoin: 'round' } )
                    )
                ),

                // Badge sandbox
                isSandbox && createElement(
                    'div',
                    { className: 'nave-sandbox-pill' },
                    createElement( 'span', { className: 'nave-sandbox-dot' } ),
                    'Modo Sandbox \u2014 Solo pruebas'
                )
            )
        );
    };

    /* ── Registro ─────────────────────────────────────── */
    registerPaymentMethod( {
        name:           'nave',
        label:          createElement( NaveLabel ),
        content:        createElement( NaveContent ),
        edit:           createElement( NaveContent ),
        canMakePayment: function() { return true; },
        ariaLabel:      'Nave',
        supports:       { features: [ 'products' ] },
    } );

} )( window.wc, window.wp );
