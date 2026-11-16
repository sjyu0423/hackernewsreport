export type FailureScenario = {
  id: string;
  title: string;
  application: string;
  tests: string;
  operations: string;
};

export const failureScenarios: FailureScenario[] = [
  {
    id: "ollama",
    title: "Ollama unavailable / model missing",
    application:
      "Hourly/daily orchestration exits with `ollama_unavailable` and does not advance watermarks.",
    tests: "Covered by orchestration unit tests with mocked Ollama failures.",
    operations:
      "Confirmable via `qwennews status` ollama probe. This site never contacts Ollama.",
  },
  {
    id: "analyze",
    title: "Article inference failure",
    application:
      "Failed analyses can remain retryable in durable processing state; watermark stays frozen while backlog remains.",
    tests: "M3.1 backlog tests cover failed → retryable → later drain behavior.",
    operations:
      "Operators inspect orchestration run records / backlog counts — not exposed on this public site.",
  },
  {
    id: "collect",
    title: "Source fetch failure",
    application:
      "If all sources fail with zero articles, outcome is `collect_failed` (not empty success) and watermarks stay put.",
    tests: "Collection/orchestration tests assert failure classification.",
    operations: "Source errors appear in status / orchestration stage detail.",
  },
  {
    id: "persist",
    title: "Report persistence failure",
    application:
      "`report_persist_failed` leaves watermarks unchanged so a partial write cannot mark work as published.",
    tests: "Report/orchestration tests cover non-advancing watermarks on persist failure.",
    operations: "Failed runs retain prior watermark timestamps.",
  },
  {
    id: "lock",
    title: "Overlapping run lock",
    application:
      "Advisory single-instance lock returns `lock_busy` so hourly and daily never run Qwen concurrently.",
    tests: "Locking tests cover busy / stale-PID recovery paths.",
    operations: "Exit code 3 on lock busy; wait for the holder to finish.",
  },
  {
    id: "db",
    title: "Missing production database",
    application:
      "As of M4.2, `run-hourly` / `run-daily` / `dashboard` refuse to start if the canonical production DB is missing.",
    tests: "Production-path checks cover fail-visible missing DB behavior.",
    operations:
      "Documented in M4.2. LaunchAgent timer success is separate evidence and was not claimed from “loaded” alone.",
  },
];

export const launchAgentHonesty =
  "M4.2 scheduler inspection recorded hourly/daily agents as not yet timer-verified (`unverified_not_yet_due` / calendar slot not observed). Do not treat LaunchAgent install as proof of a successful timer fire.";
