export function LoadingScreen() {
  return (
    <div className="h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="text-2xl font-light text-zinc-300 mb-2">&#9698; &#9698;</div>
        <p className="text-sm text-zinc-400">Loading...</p>
      </div>
    </div>
  );
}
