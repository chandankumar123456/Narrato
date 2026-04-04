import { previewImageUrl } from "../api/narrato";

export default function LivePreview({ previewUrls, totalSlides }) {
  // Determine grid: show rendered slides + skeleton placeholders
  const rendered = previewUrls.length;
  const total = totalSlides || Math.max(rendered + 4, 8);
  const skeletonCount = Math.max(0, total - rendered);

  return (
    <section className="mt-10">
      {/* Header */}
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-heading text-2xl font-semibold text-on-surface">
          Live Preview
        </h2>
        {rendered > 0 && (
          <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            {rendered} of {total} slides rendered
          </span>
        )}
      </div>

      {/* Slide Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Rendered Slides */}
        {previewUrls.map((url, i) => (
          <div
            key={url}
            className="relative rounded-xl overflow-hidden bg-on-surface shadow-ambient
              aspect-[4/3] group"
          >
            <img
              src={previewImageUrl(url)}
              alt={`Slide ${i + 1}`}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            <span
              className="absolute top-2 left-2 text-[10px] font-semibold uppercase
                bg-primary/80 text-white px-2 py-0.5 rounded"
            >
              Slide {String(i + 1).padStart(2, "0")}
            </span>
          </div>
        ))}

        {/* Skeleton Placeholders */}
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <div
            key={`skeleton-${i}`}
            className="rounded-xl overflow-hidden bg-surface-low aspect-[4/3]
              flex items-center justify-center"
          >
            {i === 0 && rendered > 0 ? (
              // First skeleton after rendered slides shows a "loading" indicator
              <div className="skeleton w-full h-full rounded-xl" />
            ) : (
              <svg
                className="w-6 h-6 text-on-surface-dim/30"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 15l5-5 4 4 4-4 5 5" />
              </svg>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
