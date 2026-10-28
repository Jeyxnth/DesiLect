/** The app's mark: a 16:9 stage with a play triangle and a caption line (same drawing as public/favicon.svg). */
export default function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <rect x="3" y="7" width="34" height="26" rx="5" fill="#1F4D45" stroke="#173B35" strokeWidth="2.5" />
      <path d="M17 13.5v9l7.5-4.5z" fill="#E2711D" />
      <rect x="10" y="26.5" width="20" height="2.5" rx="1.25" fill="#F7F3E8" />
    </svg>
  );
}
