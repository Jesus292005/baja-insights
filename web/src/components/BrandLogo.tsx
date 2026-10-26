/**
 * Baja-Insights logo (public/brand/baja-insights-logo.svg) without its background, drawn inline so it
 * follows the theme: the cream parts use the text colour and the orange parts --logo-accent.
 * The viewBox is cropped to the artwork. textLength keeps the wordmark the width of the original,
 * whichever monospaced font the browser ends up using.
 */
export function BrandLogo({ className, label = 'Baja-Insights' }: { className?: string; label?: string }) {
  return (
    <svg className={className} viewBox="400 520 1564 470" role="img" aria-labelledby="brand-logo-title">
      <title id="brand-logo-title">{label}</title>
      <g fill="currentColor">
        <circle cx="539" cy="563" r="26" />
        <circle cx="632" cy="563" r="26" />
        <circle cx="726" cy="563" r="26" opacity="0.55" />
        <circle cx="446" cy="657" r="26" />
        <circle cx="819" cy="657" r="26" opacity="0.55" />
        <circle cx="446" cy="750" r="26" />
        <circle cx="819" cy="750" r="26" opacity="0.38" />
        <circle cx="446" cy="843" r="26" opacity="0.55" />
        <circle cx="819" cy="843" r="26" opacity="0.22" />
        <circle cx="539" cy="937" r="26" opacity="0.55" />
        <circle cx="632" cy="937" r="26" opacity="0.38" />
        <circle cx="726" cy="937" r="26" opacity="0.22" />
      </g>
      <g fill="var(--logo-accent)">
        <circle cx="632" cy="750" r="26" />
        <circle cx="726" cy="843" r="26" />
        <circle cx="819" cy="937" r="37" />
      </g>
      <g fontFamily="'DejaVu Sans Mono', 'Spline Sans Mono', ui-monospace, monospace" fontSize="168">
        <text x="1033" y="710" fill="currentColor" fontWeight="700" textLength="404" lengthAdjust="spacingAndGlyphs">
          Baja
        </text>
        <text x="1033" y="915" fill="var(--logo-accent)" textLength="808" lengthAdjust="spacingAndGlyphs">
          Insights
        </text>
      </g>
      <rect x="1868" y="797" width="76" height="140" fill="var(--logo-accent)" />
    </svg>
  );
}
