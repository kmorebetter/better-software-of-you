# Transcript Format Reference

## Speaker Label Patterns

Transcripts come in many formats. Detect and handle all of these:

### Common Formats
```
Speaker 1: Hello, thanks for joining.
Sarah: Yes, happy to be here.
[Sarah Chen]: Let me share my screen.
Sarah Chen (00:01:23): The timeline looks good.
00:01:23 Sarah: I think we should...
SARAH CHEN: What about the budget?
```

### Fathom Format
```
Sarah Chen 00:00
Hello, thanks for joining today.

Kerry Morrison 00:05
Hi Sarah, excited to discuss the rebrand.
```
Speaker name on one line with timestamp, content on the next.

### Otter.ai Format
```
Sarah Chen  0:00
Hello, thanks for joining today. I wanted to discuss...

Kerry Morrison  0:15
Hi Sarah, excited to discuss the rebrand. I've been thinking about...
```
Similar to Fathom but with different timestamp formatting.

### VTT (Web Video Text Tracks)
```
WEBVTT

00:00:01.000 --> 00:00:05.000
Sarah: Hello, thanks for joining today.

00:00:05.500 --> 00:00:12.000
Kerry: Hi Sarah, excited to discuss the rebrand.
```

### SRT (SubRip Subtitle)
```
1
00:00:01,000 --> 00:00:05,000
Sarah: Hello, thanks for joining today.

2
00:00:05,500 --> 00:00:12,000
Kerry: Hi Sarah, excited to discuss the rebrand.
```

### Raw / No Labels
```
Hello, thanks for joining today. I wanted to discuss the rebrand timeline.
Hi Sarah, excited to discuss this. I've been thinking about the approach...
```
When there are no speaker labels, use context clues (the user said who the call was with) and turn-taking patterns to infer speakers.

## Duration Estimation

- If timestamps are available, calculate from first to last
- If not, estimate: average speaking rate is ~150 words per minute. Divide total word count by 150 for approximate minutes.

## Speaker Matching

When matching speaker labels to contacts:
1. Exact name match
2. First name match (if unambiguous)
3. Fuzzy match (handle typos, abbreviations)
4. If no match, ask the user
