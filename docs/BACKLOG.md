# RSS Backlog

Items queued for future work. Not prioritized — order reflects discovery date.

## Config consolidation: .conf vs config.json

**Priority:** Before next site onboarding
**Context:** Sites currently have two config sources: `sites/<slug>.conf` (shell-style KEY=VALUE, read by `lib/site_config.py`) and `sites/<slug>/config.json` (nested JSON, read directly by pipeline tools). The vertical loader needed a three-source fallback (.conf flat → .conf nested → JSON) because different fields live in different files.

**Problem:** This split creates a recurring bug class. Any new config field must be added to both files, and any loader must check both. The vertical-overlays feature shipped without the JSON fallback and would have silently dropped RE rules for LRG if not caught.

**Fix:** Choose one authoritative source per site (JSON is the natural winner — it supports nesting, is already used by the pipeline, and matches the config.json convention). Migrate all .conf fields to JSON, update `load_site_config` to read JSON, and deprecate .conf files. The .conf files can remain as read-only references during the transition.

**Affected sites:** TLN (has both), LRG (has both), VALN (.conf only), Canopy (.conf only), GFP (.conf only). TLN and LRG already have JSON configs; VALN/Canopy/GFP need JSON configs created during onboarding.
