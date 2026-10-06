# Tests

This file documents every automated test in the suite, grouped by module, with
a plain-language description of what each one verifies.

**Maintenance rule:** whenever a test is added, removed, or renamed, update this
file in the same change so it stays an accurate map of the suite.

Run everything with:

```bash
.venv/bin/python -m pytest -q
```

Tests marked **[ffmpeg]** actually run `ffmpeg`/`ffprobe` against short clips
generated on the fly (see `tests/conftest.py`); they auto-skip if those binaries
aren't on `PATH`. All other tests are pure and need no external tools or network
(OpenRouter calls are exercised through an in-memory mock transport).

**Total: 99 tests (plus 2 skipped placeholders).**

---

## tests/test_config.py — settings & model-list cache (4)

Covers the on-disk model cache that keeps the Settings dropdowns populated
between sessions.

- **test_slim_models_keeps_only_needed_fields** — the cache trims each model down
  to just `id`, `pricing.prompt`, and `architecture.input_modalities` (the fields
  the dropdowns and filters use), discarding the rest.
- **test_slim_models_skips_entries_without_id** — models with no `id` are dropped
  rather than cached as junk.
- **test_cache_round_trips** — saving models then loading them back returns the
  same models.
- **test_load_cached_models_returns_empty_when_missing** — loading a cache file
  that doesn't exist returns an empty list instead of erroring.

---

## tests/test_ffmpeg.py — ffprobe parsing, command builders, real runs (21)

### ffprobe JSON parsing (pure)

- **test_parse_probe_reads_video_codec_and_size** — pulls codec name, width, and
  height out of ffprobe's JSON.
- **test_parse_probe_reads_duration_as_float** — reads the clip duration as a
  number.
- **test_parse_probe_detects_audio_track_present** — reports `has_audio=True` when
  an audio stream exists.
- **test_parse_probe_detects_audio_track_absent** — reports `has_audio=False` when
  there's no audio stream.
- **test_parse_probe_reads_hevc_codec** — recognizes an HEVC (H265) video stream.
- **test_parse_probe_raises_when_no_video_stream** — raises a clear error if the
  file has no video stream at all.
- **test_parse_probe_falls_back_to_stream_duration** — if the container has no
  duration, it falls back to the video stream's duration.

### Command builders (pure)

- **test_thumbnail_command_seeks_before_input** — the thumbnail command puts `-ss`
  before `-i` (fast seek to the wanted frame).
- **test_thumbnail_command_scales_to_720_and_grabs_one_frame** — thumbnails are
  scaled to 720p and only one frame is grabbed.
- **test_convert_command_uses_h264_crf18_and_drops_audio** — the H265→H264 convert
  command uses libx264 at CRF 18 and strips audio (`-an`).
- **test_strip_audio_command_copies_video_and_drops_audio** — the strip-audio
  command copies the video stream untouched and drops audio (no re-encode).
- **test_thumbnail_positions_are_four_spread_through_the_clip** — there are exactly
  four thumbnail positions, all strictly between the start and end of the clip.

### Real ffmpeg runs **[ffmpeg]**

- **test_probe_real_h264_clip_with_audio** — probing a real H264+audio clip reports
  the right codec, audio present, and ~correct duration.
- **test_probe_real_hevc_clip_without_audio** — probing a real HEVC silent clip
  reports HEVC and no audio.
- **test_probe_raises_on_missing_file** — probing a path that doesn't exist raises
  a clear error.
- **test_generate_thumbnails_creates_four_png_files** — generates four non-empty
  PNG thumbnails from a real clip.
- **test_generate_thumbnails_are_720_high** — the generated thumbnails are 720px
  tall.
- **test_convert_produces_h264_without_audio** — converting a real HEVC clip yields
  an H264 file with no audio.
- **test_strip_audio_removes_audio_and_keeps_h264** — stripping audio from a real
  H264+audio clip removes the audio while leaving the video as H264.
- **test_convert_leaves_no_output_or_temp_on_failure** — a failed conversion leaves
  neither a partial output file nor a leftover temp file (atomic write).
- **test_terminate_all_is_a_noop_when_nothing_running** — calling the shutdown
  process-killer with nothing running doesn't error.

---

## tests/test_library.py — local persistence of AI fields (9)

Covers saving/reloading generated text fields keyed by filename.

- **test_lookup_returns_none_for_unseen_filename** — an unknown filename returns
  nothing.
- **test_record_then_lookup_round_trips** — recording fields for a filename and
  looking them up returns them.
- **test_data_persists_across_instances** — data written by one `Library` instance
  is readable by a fresh instance (survives app restart).
- **test_item_fields_captures_ai_fields_only** — only the AI text fields
  (description, title, title candidates, tags, category) are captured — not
  thumbnails or stats.
- **test_apply_fields_restores_values** — restoring stored fields onto an item sets
  its values back.
- **test_apply_fields_sets_tagged_stage_when_tags_present** — an item restored with
  tags is marked as at the "tagged" stage.
- **test_apply_fields_sets_described_stage_when_only_description** — an item
  restored with only a description is marked at the "described" stage.
- **test_has_data_false_for_all_empty** — an all-empty field set is treated as
  "nothing to save".
- **test_has_data_true_when_any_field_present** — any non-empty field counts as
  worth saving.

---

## tests/test_openrouter.py — AI client: prompts, parsing, HTTP (39)

### Prompt builders (pure)

- **test_describe_messages_include_each_image_as_image_url** — the vision request
  includes every thumbnail as an `image_url` entry.
- **test_describe_messages_lead_with_a_text_instruction** — the vision request
  starts with a text instruction before the images.
- **test_titles_messages_request_the_configured_count** — the titles prompt asks
  for the configured number of titles and includes the description.
- **test_tags_messages_request_the_configured_count** — the tags prompt asks for
  the configured number (45) of keywords.
- **test_category_messages_list_the_allowed_categories** — the category prompt
  lists the allowed Envato categories.

### Custom prompt templates (pure)

- **test_titles_messages_use_custom_prompt_with_placeholders** — a custom titles
  prompt has its `{count}` and `{description}` placeholders filled in.
- **test_tags_messages_use_custom_prompt_with_placeholders** — a custom tags prompt
  has its `{count}`, `{title}`, and `{description}` placeholders filled in.
- **test_describe_messages_use_custom_instruction** — a custom description prompt
  replaces the default instruction text.
- **test_custom_prompt_with_stray_braces_does_not_crash** — unknown `{tokens}` in a
  custom prompt are left as-is rather than causing an error.

### Response parsing (pure)

- **test_parse_titles_reads_a_json_array** — parses titles from a JSON array.
- **test_parse_titles_reads_a_fenced_json_array** — parses titles from a JSON array
  wrapped in a ```` ```json ```` code fence.
- **test_parse_titles_falls_back_to_numbered_lines** — if not JSON, parses a
  numbered list of titles.
- **test_parse_titles_strips_bullets_and_quotes** — strips leading bullets and
  surrounding quotes from title lines.
- **test_parse_tags_splits_and_trims** — splits a comma-separated line into trimmed
  keywords.
- **test_parse_tags_removes_duplicates_case_insensitively** — collapses duplicate
  keywords ignoring case.
- **test_parse_tags_strips_a_code_fence** — removes a surrounding code fence before
  splitting tags.
- **test_parse_category_exact_match** — accepts an exact category name.
- **test_parse_category_is_case_insensitive** — matches a category regardless of
  case.
- **test_parse_category_finds_name_inside_a_sentence** — extracts a valid category
  even when the model wraps it in a sentence.
- **test_parse_category_raises_on_unknown** — raises if the model returns a
  category not on the allowed list.
- **test_encode_image_produces_a_png_data_url** — encodes an image file into a
  base64 `data:image/png;base64,...` URL that round-trips back to the bytes.

### HTTP boundary (mocked transport, no network)

- **test_chat_returns_text_and_cost** — a chat call returns the model's text and
  the charged cost from `usage.cost`.
- **test_chat_sends_bearer_auth_header** — the request sends `Authorization:
  Bearer <key>`.
- **test_chat_raises_on_error_status** — a non-200 response raises an error that
  includes the API's message.
- **test_chat_without_key_raises_before_request** — calling with no API key errors
  before any network request is made.
- **test_list_models_returns_the_data_array** — listing models returns the `data`
  array from the response.
- **test_titles_call_parses_json_array_from_response** — the end-to-end titles call
  parses a JSON array from the mocked response.
- **test_tags_call_parses_comma_list_from_response** — the end-to-end tags call
  parses a comma-separated list from the mocked response.
- **test_categorize_call_matches_allowed_category** — the end-to-end categorize
  call returns a valid category.

### Keyword limit (pure)

- **test_tags_over_limit_zero_within_limit** — 45 keywords, and exactly the hard
  limit (50), count as zero over the limit.
- **test_tags_over_limit_counts_excess_above_fifty** — 53 keywords reports 3 over
  the limit.

### Model-list filtering (pure)

- **test_is_free_model_by_zero_prompt_price** — a model is "free" only when its
  prompt price is zero.
- **test_supports_text_excludes_generators** — a text model outputs text and isn't
  an image or audio generator.
- **test_supports_vision_needs_image_in_and_text_out** — vision means it accepts
  image input and replies with text.
- **test_supports_vision_excludes_image_generators** — a model that takes an image
  but outputs an image is a generator, not recognition.
- **test_filter_models_free_only** — the free filter keeps only zero-price models.
- **test_filter_models_paid_only** — the paid filter keeps only priced models.
- **test_filter_models_vision_keeps_both_prices_excludes_generators** — the vision
  filter keeps vision models at any price but drops generators.
- **test_filter_models_text_excludes_image_generators** — the text filter keeps
  text models and drops image/audio generators.

---

## tests/test_csv_export.py — Envato CSV writer (11)

- **test_columns_match_the_envato_header_in_order** — the first seven columns and
  the last column are exactly right, and there are 25 columns total.
- **test_build_row_maps_pipeline_fields** — Title, Description, Keywords, and
  Category come from the item's pipeline fields.
- **test_build_row_description_falls_back_to_title_when_empty** — when a clip has
  no description, the Description column uses the title instead of being blank.
- **test_build_row_uses_fixed_prices** — single-use price is 11 and multi-use is 22.
- **test_missing_fields_empty_for_complete_item** — a fully-filled clip reports no
  missing fields.
- **test_missing_fields_lists_each_empty_field** — an empty clip reports Title,
  Description, Keywords, and Category as missing (drives the export warning).
- **test_build_row_filename_is_original_when_not_processed** — Filename is the
  original name when the clip wasn't converted/stripped.
- **test_build_row_filename_is_processed_output_when_present** — Filename is the
  processed output name (e.g. the `.mov`) when there is one.
- **test_build_row_leaves_other_columns_blank** — all non-pipeline columns (Color,
  Pace, Setting, Location, Releases, …) are blank.
- **test_write_csv_round_trips_with_quoted_keywords** — a written CSV reads back
  correctly, keeping comma-containing keywords in a single cell.
- **test_write_csv_writes_header_only_for_empty_list** — exporting no items writes
  just the header row.

---

## tests/test_stats.py — usage stats (cost, time & ratings) (6)

- **test_summary_none_when_no_data** — asking for a model/query with no history
  returns nothing.
- **test_record_then_summary_averages** — two recorded calls average their cost and
  response time correctly.
- **test_query_types_are_tracked_separately** — description/titles/tags/category
  costs are kept per query type, not pooled.
- **test_all_summaries_lists_every_model_and_type** — the full summary lists one row
  per model+query type, sorted.
- **test_record_rating_counts_good_and_bad** — thumbs-up/down ratings accumulate as
  good/bad counts for a model+query type.
- **test_stats_persist_across_instances** — recorded stats survive an app restart.

---

## tests/test_local_vision.py — local provider stub (2, +2 skipped)

- **test_describe_stub_raises_not_implemented** — the local describe stub raises
  until a backend is wired in.
- **test_tags_stub_raises_not_implemented** — the local tagger stub raises until a
  backend is wired in.
- *(skipped)* **test_local_description_quality_vs_cloud** — placeholder for the
  future local-vs-cloud description benchmark.
- *(skipped)* **test_local_tag_quality_vs_cloud** — placeholder for the future
  local-vs-cloud tag benchmark.

---

## tests/test_queue.py — convert/strip-audio queue (5)

- **test_output_path_for_convert_is_mov** — a convert job writes to
  `converted/<name>.mov`.
- **test_output_path_for_strip_keeps_original_extension** — a strip-audio job keeps
  the original container extension in `converted/`.
- **test_process_item_without_op_raises** — processing an item with no queued
  operation raises rather than doing nothing silently.
- **test_process_item_converts_hevc_to_h264_muted** **[ffmpeg]** — processing a
  real HEVC clip produces a muted H264 output.
- **test_process_item_strips_audio_from_h264** **[ffmpeg]** — processing a real
  H264+audio clip produces an output with no audio.


## tests/test_models.py — VideoItem derived properties (2)

- **test_size_mb_reports_file_size_in_megabytes** — `size_mb` divides the on-disk
  byte size by 1024² to report megabytes.
- **test_size_mb_is_none_when_file_missing** — `size_mb` returns None when the file
  can't be read (e.g. an unmounted external drive).
