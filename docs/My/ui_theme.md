# Grounded interface design system

## Visual principles

The interface is minimal, editorial, search-first, and evidence-led. The current implementation follows the local reference mockup in `ui/Legal Document Retrieval UI Design`: a legal Q&A topbar, dark blue technical sidebar, centered landing composer, verified answer card, source list, cited-evidence panel, and bounded source dialog. The empty state gives visual priority to one question composer. After submission, the question and answer replace the hero; sources support the reading flow, settings remain in the sidebar, and diagnostics remain behind tabs.

## Theme tokens

`src/ui/theme.py` is the only color, type-family, radius, shadow, and width token source. `src/ui/styles.py` turns the selected tokens into CSS variables and organized component rules. Runtime CSS extends the safe fallback in `.streamlit/config.toml`.

Light uses a white/blue palette: page `#f7fbff`, primary surface `#ffffff`, primary text `#0f172a`, muted text `#64748b`, and blue accent `#2563eb`. Dark uses navy rather than pure black: page `#0f172a`, primary surface `#111827`, primary text `#f8fafc`, muted text `#94a3b8`, and accent `#60a5fa`.

The UI no longer uses the amber/orange reference palette as the brand color. Blue is used for primary actions, citation chips, selected tabs, source metadata pills, focus rings, and evidence highlights. Green remains reserved for healthy Production status, and red remains reserved for blocked/error states.

System is the default and follows `prefers-color-scheme`. Light and Dark force their token set. Theme selection is stored separately from the conversation signature, so changing theme does not clear answers.

## Typography and spacing

The local sans stack is Work Sans when installed, followed by Inter and native UI fonts. No font is downloaded. Display, answer, and source text now use the same sans stack because some locally installed serif variants can render Vietnamese diacritics with visible gaps. Monospace is reserved for technical metadata only. Hero type scales from about 58 px desktop to 38 px mobile; answer titles and body copy prioritize stable Vietnamese rendering over decorative serif styling.

Spacing follows 4, 8, 12, 16, 24, 32, 40, 48, 64, and 80 px increments. Cards use 16–20 px internal space. Major answer sections use roughly 32–52 px separation.

## Radius and shadow

Controls use compact 7–10 px radii, answer/source cards use about 13–16 px, and composer/dialog surfaces use soft 15–16 px corners. Borders establish most hierarchy. Shadows are reserved for the composer, answer card, and elevated dialog surfaces; dark shadows are intentionally quieter.

## Page shell

The application shell now uses the full Streamlit wide canvas. Editorial reading content is capped near 930 px. When an inline citation is selected, the answer column and evidence panel split the page similarly to the reference mockup. Desktop topbar padding is 36 px, tablet 28 px, and mobile 18 px.

The 76 px topbar contains the legal app title/subtitle, visual theme/language indicators, and active-mode pill. The dark blue sidebar contains the Grounded brand, Navigation, Preferences, Runtime, Retrieval, Advanced, Actions, and Production readiness sections. All functional Streamlit controls remain real controls in the sidebar; the topbar selectors are visual mirrors for the current theme/language state.

## Landing layout and composer

The hero begins around 17% of viewport height on desktop and includes an eyebrow, one legal search question, one subtitle, one composer, short example prompts, and a compact readiness line. No diagnostics or artifact paths enter the hero.

The landing composer is a shorter legal-search textarea inside a rounded white/blue elevated surface. Its toolbar shows mode/config context, a keyboard hint, and one Ask action. The Ask button submits; Shift+Enter creates a line break where the browser supports native textarea behavior.

## Answer layout

The page becomes a research thread rather than a chat transcript. Each turn uses a legal-query eyebrow with date, question heading, status row, verified answer card, answer actions, selectable exploration prompts, follow-up composer, and secondary tabs. There are no alternating chat bubbles or duplicated landing composers.

## Citations and sources

Validated citations are native Streamlit buttons styled as compact blue pills; they are not anchors and contain no source URL. Model output is never passed to unsafe HTML. Clicking a pill selects only the matching turn-local citation and shows a right-side cited-evidence panel on the current page when desktop width allows it.

The Sources tab contains only authoritative cited-source objects first, rendered as legal document rows with citation ID, document icon, title, article/detail pill, score/rank/evidence metadata, preview text, and **View source** action. Its primary **View source** control opens a large `st.dialog` containing the full carried chunk and metadata. A visually secondary **Open original document ↗** link appears only when a Production source has a validated real URL. Uncited retrieved context is separated and visually quieter. Demo sources retain explicit mock labeling where applicable and never expose an external-document action.

Citation pills are touch-friendly internal controls backed by turn-aware session state. The right-side cited-evidence panel shows the selected source title, detail, confidence pill, source text, and actions. The full-source dialog is bounded to about 860 px and 88 vh on desktop, becomes near-full-width on mobile, and scrolls long source content internally. Full-source content wraps and preserves line breaks. Valid exact spans use a restrained light-blue surface with a stronger blue bottom border. All source characters are escaped before application-owned HTML wrappers. Missing or invalid spans render through readable source text with no guessed highlight. Explicit Close controls clear the selection while preserving the answer and conversation; exact scroll restoration remains subject to Streamlit rerun behavior.

## Sidebar and diagnostics

Sidebar sections are Navigation, Preferences, Runtime, Retrieval, Model & hyperparameters, Advanced, Actions, and Production readiness. Graph + RRF + reranker remains available through the existing runtime toggle when the graph artifact is present; the toggle is disabled with an explanation when the graph pickle is missing. Readiness defaults to a compact ready-count and bounded status list; paths and blockers are in an expander.

The Model & hyperparameters section exposes bounded runtime overrides for generation:

- Model selector: current config model, `env:LLM_BASE_MODEL`, `env:LLM_LARGER_MODEL`, or a custom model ID supported by the configured OpenAI-compatible endpoint.
- Prompt strategy: `base` or `reasoning`.
- Decoding controls: temperature, top-p, maximum output tokens, timeout seconds, and retry count.

These controls build an in-memory effective config for the current Streamlit session and submission. They do not write back to `configs/ablation_configs.yaml`, `.env`, or any teammate artifact. API keys and base URLs remain environment-driven and are not displayed in the UI. Production readiness and resource caching use the same effective config so the user sees blockers for the exact model/hyperparameter state they are about to run.

Sources, Details, Latency, Agent trace, and Diagnostics appear after the answer. Latency uses small applicable-stage cards and marks demo timings. Agent steps are structured cards, with bounded raw rows nested in an expander. Safe raw diagnostics require the Show diagnostics toggle.

## Responsive behavior

- Desktop (`min-width: 1024px`): full shell, 930 px reading column, optional right-side evidence panel, legal source rows.
- Tablet (`max-width: 1023px`): compact dark rail, available-width reading content, preserved Streamlit controls where space allows.
- Mobile (`max-width: 640px`): sidebar hidden, compact topbar, stacked content, full-width controls, and overflow containment.

## Accessibility and motion

Mode includes text rather than color alone. Controls have semantic Streamlit labels and at least 44 px mobile targets. Keyboard focus receives a visible accent outline. Source previews expose all essential information without hover. Body and muted text use contrast-aware theme tokens. `prefers-reduced-motion` disables transitions and animations.

## Demo and Production

Both providers use the same response and component tree. Demo is labeled in the header, status row, sources, trace, and timing. Production cannot accept a mock-marked response. Auto changes provider metadata only; compatible teammate artifacts do not require a presentation rewrite.

Demo Preview can now read local mock QA rows from `data/qa_final.jsonl`. This lets teammates test the full UI without configuring a real LLM API key, base URL, FAISS index, reranker model, or graph artifact. The demo provider matches the submitted question against the local QA dataset, returns the recorded `reference_answer`, and builds mock cited-source cards from `ground_truth` ids plus the recorded explanation. Because `qa_final.jsonl` does not contain the original full legal chunk text, these sources are explicitly marked as mock QA evidence and should not be treated as authoritative legal text.

To test the UI without a real API:

1. Start Streamlit normally with `streamlit run ui/app.py`.
2. Select `Demo Preview` in the Runtime mode selector.
3. Use one of the landing example cards loaded from `data/qa_final.jsonl`, or paste a similar Vietnamese question from that file.

No production API call is performed in this path. Diagnostics include `production_call_performed: false` and a `demo_scenario` value beginning with `qa-final:` when the answer came from the mock QA dataset. If the dataset is missing or the question does not match it closely enough, the provider falls back to the older deterministic design-preview scenarios.

## Recent UI Refresh

The August 24 UI refresh adapted the reference implementation from `ui/Legal Document Retrieval UI Design` into the existing Streamlit app instead of replacing the app with a separate React frontend. The implementation changed presentation only:

- `ui/app.py` keeps the canonical Streamlit entry point, runtime mode handling, cache controls, resource loading, and production submission path.
- `src/ui/components.py` now renders the legal Q&A topbar, dark blue sidebar brand, centered landing experience, verified answer card, legal source rows, right-side cited-evidence panel, and redesigned source dialog.
- `src/ui/styles.py` contains the visual implementation for the reference-inspired shell using the white/blue palette.
- `src/ui/theme.py` stores the white/blue Light tokens and navy Dark tokens.
- `src/ui/i18n.py` keeps English/Vietnamese UI copy for the new labels.

The refresh intentionally preserves existing behavior:

- Demo Preview, Production, and Auto modes still use the same provider contract.
- Named configuration, Top-k, filter profile, model selector, prompt strategy, generation hyperparameters, Graph + RRF + reranker, diagnostics, cache clearing, new search, and conversation clearing remain available.
- Production readiness checks, FAISS artifact checks, environment loading, and D-drive local cache behavior are unchanged.
- Inline citations remain native Streamlit buttons with turn-local source selection.
- Full source viewing still uses normalized response data already carried by the answer; the UI does not fetch or reconstruct source content.
- Source text formatting, evidence highlighting, diagnostics gating, safe error rendering, and secret redaction remain in place.

## Internal design preview

Open `?preview=design-system` to render the component gallery. It uses `DemoAnswerProvider` only and shows tokens, typography, controls, badges, answer copy, citations, source cards, suggestions, latency, trace, abstention, blocked, and error states. `?preview=landing` renders the production-independent empty-state fixture. Use the sidebar Theme selector to review System, Light, and Dark; `&theme=Light` or `&theme=Dark` is available for deterministic visual-QA captures.

## Streamlit selector limitations

CSS relies primarily on stable `data-testid` selectors. The `:has(.ga-answer-marker)` rule is a cosmetic enhancement for answer typography, and the column/test-id rules are version-sensitive. Each failure degrades to usable native Streamlit rendering. Application-owned classes control the header, hero, mode pills, source typography, states, and metrics.

## Screenshot procedure and checklist

Run `streamlit run ui/app.py`, then capture the landing, multi-citation answer, dark theme, mobile landing/answer, and Production-blocked state at 1440×1000, 1024×900, and 390×844. Store captures in a temporary directory.

Review header quietness, hero balance, composer dominance, reading width, citation alignment, source-card rhythm, tab hierarchy, dark contrast, horizontal overflow, mobile touch sizes, Demo labels, and exact Production blockers. A startup probe without browser capture is not screenshot validation.

To change the design, edit tokens first. Add component CSS only when a relationship cannot be expressed through existing variables; do not scatter palette values through `ui/app.py`.
