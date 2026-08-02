# Grounded interface design system

## Visual principles

The interface is minimal, editorial, search-first, and evidence-led. The empty state gives visual priority to one question composer. After submission, the question and answer replace the hero; sources support the reading flow, settings remain in the sidebar, and diagnostics remain behind tabs.

## Theme tokens

`src/ui/theme.py` is the only color, type-family, radius, shadow, and width token source. `src/ui/styles.py` turns the selected tokens into CSS variables and organized component rules. Runtime CSS extends the safe fallback in `.streamlit/config.toml`.

Light uses warm neutrals: page `#f7f7f5`, primary surface `#ffffff`, primary text `#171714`, muted text `#74746c`, and restrained teal accent `#1f766f`. Dark uses charcoal rather than black: page `#111311`, primary surface `#181b18`, primary text `#f1f2ed`, muted text `#92968b`, and accent `#75bdb5`.

System is the default and follows `prefers-color-scheme`. Light and Dark force their token set. Theme selection is stored separately from the conversation signature, so changing theme does not clear answers.

## Typography and spacing

The local system sans stack is Inter when installed, followed by native UI fonts. No font is downloaded. Monospace is reserved for technical content. Hero type scales from 56 px desktop to 32 px mobile; question titles range from 34 to 29 px; answer copy is 17.5 px with 1.78 line height; metadata is 11–13 px.

Spacing follows 4, 8, 12, 16, 24, 32, 40, 48, 64, and 80 px increments. Cards use 16–20 px internal space. Major answer sections use roughly 32–52 px separation.

## Radius and shadow

Controls use 9–13 px radii, cards 17 px, hero forms 23 px, and badges 999 px. Borders establish most hierarchy. Shadows are reserved for the composer, sticky header, and elevated surfaces; dark shadows are intentionally quieter.

## Page shell

The application shell is capped at 1260 px. Editorial reading content is capped at 790 px. Source rails can use the wider shell. Desktop padding is 48 px, tablet 24 px, and mobile 16 px.

The 60 px sticky header contains a CSS geometric mark, product name, and active-mode pill. Product actions and all technical controls remain in the redesigned 320–340 px collapsible sidebar.

## Landing layout and composer

The hero begins around 11% of viewport height on desktop and includes an eyebrow, one question, one subtitle, one composer, short example prompts, and a compact readiness line. No diagnostics or artifact paths enter the hero.

The composer is a 126 px multiline textarea inside a 23 px rounded elevated surface. Its toolbar shows mode/config context and one Ask action. The Ask button submits; Shift+Enter creates a line break where the browser supports native textarea behavior.

## Answer layout

The page becomes a research thread rather than a chat transcript. Each turn uses a question heading, status row, editorial answer, cited-source rail, selectable exploration prompts, follow-up composer, and secondary tabs. There are no alternating chat bubbles or duplicated landing composers.

## Citations and sources

Validated citations are native Streamlit buttons styled as compact pills; they are not anchors and contain no source URL. Model output is never passed to unsafe HTML. Clicking a pill selects only the matching turn-local citation and shows a compact preview on the current page.

The cited rail contains only authoritative cited-source objects. Its primary **View source** control opens a large `st.dialog` containing the full carried chunk and metadata. A visually secondary **Open original document ↗** link appears only when a Production source has a validated real URL. Uncited retrieved context is separated and visually quieter. Demo sources retain an explicit DEMO SOURCE label and never expose an external-document action.

Citation pills are touch-friendly internal controls backed by turn-aware session state. The full-source dialog is bounded to about 860 px and 86 vh on desktop, becomes near-full-width on mobile, and scrolls long source content internally. Full-source content wraps and preserves line breaks. Valid exact spans use a restrained warm-yellow/amber surface with a stronger bottom border; dark mode uses the same theme-aware warning token without glow. All source characters are escaped before application-owned HTML wrappers. Missing or invalid spans render through native plain text with no highlight. Explicit Close controls clear the selection while preserving the answer and conversation; exact scroll restoration remains subject to Streamlit rerun behavior.

## Sidebar and diagnostics

Sidebar sections are Runtime, Retrieval, Advanced, Actions, and Production readiness. Graph and Reranker are disabled with explanations until adapters exist. Readiness defaults to a compact ready-count and bounded status list; paths and blockers are in an expander.

Sources, Details, Latency, Agent trace, and Diagnostics appear after the answer. Latency uses small applicable-stage cards and marks demo timings. Agent steps are structured cards, with bounded raw rows nested in an expander. Safe raw diagnostics require the Show diagnostics toggle.

## Responsive behavior

- Desktop (`min-width: 1024px`): full shell, 790 px reading column, multi-column source rail.
- Tablet (`max-width: 1023px`): 24 px page padding, 38 px hero, available-width reading content.
- Mobile (`max-width: 640px`): 16 px padding, 32 px hero, stacked source cards, full-width touch controls, compact brand, and overflow containment.

## Accessibility and motion

Mode includes text rather than color alone. Controls have semantic Streamlit labels and at least 44 px mobile targets. Keyboard focus receives a visible accent outline. Source previews expose all essential information without hover. Body and muted text use contrast-aware theme tokens. `prefers-reduced-motion` disables transitions and animations.

## Demo and Production

Both providers use the same response and component tree. Demo is labeled in the header, status row, sources, trace, and timing. Production cannot accept a mock-marked response. Auto changes provider metadata only; compatible teammate artifacts do not require a presentation rewrite.

## Internal design preview

Open `?preview=design-system` to render the component gallery. It uses `DemoAnswerProvider` only and shows tokens, typography, controls, badges, answer copy, citations, source cards, suggestions, latency, trace, abstention, blocked, and error states. `?preview=landing` renders the production-independent empty-state fixture. Use the sidebar Theme selector to review System, Light, and Dark; `&theme=Light` or `&theme=Dark` is available for deterministic visual-QA captures.

## Streamlit selector limitations

CSS relies primarily on stable `data-testid` selectors. The `:has(.ga-answer-marker)` rule is a cosmetic enhancement for answer typography, and the column/test-id rules are version-sensitive. Each failure degrades to usable native Streamlit rendering. Application-owned classes control the header, hero, mode pills, source typography, states, and metrics.

## Screenshot procedure and checklist

Run `streamlit run ui/app.py`, then capture the landing, multi-citation answer, dark theme, mobile landing/answer, and Production-blocked state at 1440×1000, 1024×900, and 390×844. Store captures in a temporary directory.

Review header quietness, hero balance, composer dominance, reading width, citation alignment, source-card rhythm, tab hierarchy, dark contrast, horizontal overflow, mobile touch sizes, Demo labels, and exact Production blockers. A startup probe without browser capture is not screenshot validation.

To change the design, edit tokens first. Add component CSS only when a relationship cannot be expressed through existing variables; do not scatter palette values through `ui/app.py`.
