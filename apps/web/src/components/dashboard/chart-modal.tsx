"use client";

interface Props {
  ticker: string;
  onClose: () => void;
}

export default function ChartModal({ ticker, onClose }: Props) {
  const src = `https://www.tradingview.com/widgetembed/?symbol=${encodeURIComponent(ticker)}&interval=D&theme=dark&style=1&locale=en&hide_side_toolbar=0&allow_symbol_change=0&save_image=0&withdateranges=1`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-background border border-border rounded-lg overflow-hidden flex flex-col"
        style={{ width: "min(960px, 95vw)", height: "min(620px, 90vh)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center px-4 py-2 border-b border-border shrink-0">
          <span className="text-sm font-semibold">
            {ticker}{" "}
            <span className="text-muted-foreground font-normal text-xs">
              Daily
            </span>
          </span>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl leading-none"
          >
            ×
          </button>
        </div>
        <iframe
          src={src}
          className="flex-1 w-full border-0"
          allow="fullscreen"
          title={`${ticker} chart`}
        />
      </div>
    </div>
  );
}
