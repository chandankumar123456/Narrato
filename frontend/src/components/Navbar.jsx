import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="w-full bg-surface-lowest/80 backdrop-blur-[24px] sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-8">
          <Link
            to="/"
            className="font-heading text-on-surface font-bold text-lg tracking-tight no-underline"
          >
            Narrato
          </Link>

          {/* Nav Links */}
          <div className="hidden sm:flex items-center gap-6">
            <a
              href="#"
              className="text-sm font-medium text-primary no-underline border-b border-primary pb-0.5"
            >
              Features
            </a>
            <a
              href="#"
              className="text-sm font-medium text-on-surface-variant no-underline hover:text-on-surface transition-colors"
            >
              Pricing
            </a>
            <a
              href="#"
              className="text-sm font-medium text-on-surface-variant no-underline hover:text-on-surface transition-colors"
            >
              Docs
            </a>
          </div>
        </div>

        {/* CTA */}
        <Link
          to="/"
          className="bg-primary text-white text-sm font-semibold px-5 py-2 rounded-lg no-underline hover:bg-primary-hover transition-colors"
        >
          Try Now
        </Link>
      </div>
    </nav>
  );
}
