export default function Footer() {
  return (
    <footer className="mt-auto bg-surface-lowest py-6 px-6">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <p className="text-xs text-on-surface-variant">
          © 2024 Narrato AI. All rights reserved.
        </p>
        <div className="flex items-center gap-6">
          <a
            href="#"
            className="text-xs text-on-surface-variant no-underline hover:text-on-surface transition-colors"
          >
            Legal
          </a>
          <a
            href="#"
            className="text-xs text-on-surface-variant no-underline hover:text-on-surface transition-colors"
          >
            Support
          </a>
        </div>
      </div>
    </footer>
  );
}
