import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loader2 } from "lucide-react";

interface StreamingTextProps {
  content: string;
  isStreaming: boolean;
}

/**
 * Splits content into tool-indicator lines ("*Using contacts...*")
 * and regular markdown blocks. Tool indicators are rendered as styled
 * chips; everything else goes through ReactMarkdown.
 */
export function StreamingText({ content, isStreaming }: StreamingTextProps) {
  const segments = useMemo(() => parseSegments(content), [content]);

  return (
    <div className="text-sm">
      {segments.map((seg, i) =>
        seg.type === "tool" ? (
          <span
            key={i}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-500 bg-zinc-50 border border-zinc-200 rounded-full px-2.5 py-1 my-1 mr-1"
          >
            <Loader2 size={10} className="animate-spin" />
            {seg.text}
          </span>
        ) : (
          <div key={i} className="prose prose-zinc prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {seg.text}
            </ReactMarkdown>
          </div>
        ),
      )}
      {isStreaming && (
        <span className="inline-block w-1.5 h-4 bg-zinc-400 animate-pulse ml-0.5 align-text-bottom rounded-sm" />
      )}
    </div>
  );
}

interface Segment {
  type: "tool" | "markdown";
  text: string;
}

// Matches lines like "*Using contacts...*" or "*Using get_profile...*"
const TOOL_RE = /^\*Using\s+[\w_]+\.\.\.\*$/;

function parseSegments(content: string): Segment[] {
  const lines = content.split("\n");
  const segments: Segment[] = [];
  let buffer = "";

  for (const line of lines) {
    if (TOOL_RE.test(line.trim())) {
      // Flush any accumulated markdown
      if (buffer.trim()) {
        segments.push({ type: "markdown", text: buffer.trim() });
        buffer = "";
      }
      // Extract the tool name (strip the * wrappers)
      const name = line.trim().slice(1, -1); // "Using contacts..."
      segments.push({ type: "tool", text: name });
    } else {
      buffer += (buffer ? "\n" : "") + line;
    }
  }

  // Flush remaining markdown
  if (buffer.trim()) {
    segments.push({ type: "markdown", text: buffer.trim() });
  }

  return segments;
}
