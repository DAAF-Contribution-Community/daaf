/* §§ FILE_HEADER ====================================================
   DAAF Pipeline Explainer — application logic (2026-04-17b version)
   See DESIGN_DOCUMENT.md for architecture rationale.
   Run `Grep §§` on this file to get a navigable section index.
   ================================================================ */
(function () {
    'use strict';

    // §§ CONSTANTS (config + URL bases + FIGURES/AGENT_SPECS/SKILL_SPECS maps + USER_PROMPT) ===
    const GITHUB_RAW_BASE  = 'https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/';
    const GITHUB_BLOB_BASE = 'https://github.com/DAAF-Contribution-Community/daaf/blob/main/';
    const RESEARCH_PREFIX  = 'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/';
    // LOG_DIR is the path (under GITHUB_RAW_BASE) to the JSONL session
    // log files in the DAAF repo. Used by fetchLogLine() to resolve
    // orchestratorLogLine.path references in PIPELINE_STEPS.
    const LOG_DIR          = RESEARCH_PREFIX + 'logs/';
    const FIGURE_BASE      = GITHUB_RAW_BASE + RESEARCH_PREFIX + 'output/figures/';
    const REPORT_BLOB_URL  = GITHUB_BLOB_BASE + RESEARCH_PREFIX + '2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md';
    // Path (without raw base) used by fetchDocument() to load the full
    // report markdown into the right panel when the intro is active.
    const REPORT_PATH      = RESEARCH_PREFIX + '2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md';
    const NAV_HEIGHT       = 88;
    const SCROLL_DEBOUNCE  = 120;
    const FOCUS_LINE_RATIO = 0.35;
    const FADE_MS          = 150;
    const NAV_LOCK_MS      = 800;

    const FIGURES = {
        grad_rate_vs_admission_rate:      FIGURE_BASE + '2026-03-29_grad_rate_vs_admission_rate.png',
        boxplot_grad_rate_by_selectivity: FIGURE_BASE + '2026-03-29_boxplot_grad_rate_by_selectivity.png',
        heatmap_selectivity_pell:         FIGURE_BASE + '2026-03-29_heatmap_selectivity_pell.png',
        correlation_heatmap:              FIGURE_BASE + '2026-03-29_correlation_heatmap.png',
        sector_comparison:                FIGURE_BASE + '2026-03-29_sector_comparison.png',
        actual_vs_predicted:              FIGURE_BASE + '2026-03-29_actual_vs_predicted.png',
    };

    const AGENT_SPECS = {
        'orchestrator':         '.claude/skills/daaf-orchestrator/SKILL.md',
        'search-agent':         '.claude/agents/search-agent.md',
        'source-researcher':    '.claude/agents/source-researcher.md',
        'data-planner':         '.claude/agents/data-planner.md',
        'plan-checker':         '.claude/agents/plan-checker.md',
        'research-executor':    '.claude/agents/research-executor.md',
        'code-reviewer':        '.claude/agents/code-reviewer.md',
        'report-writer':        '.claude/agents/report-writer.md',
        'data-verifier':        '.claude/agents/data-verifier.md',
        'notebook-assembler':   '.claude/agents/notebook-assembler.md',
        'research-synthesizer': '.claude/agents/research-synthesizer.md',
        'debugger':             '.claude/agents/debugger.md',
    };

    const SKILL_SPECS = {
        'education-data-explorer':        '.claude/skills/education-data-explorer/SKILL.md',
        'education-data-query':           '.claude/skills/education-data-query/SKILL.md',
        'education-data-context':         '.claude/skills/education-data-context/SKILL.md',
        'education-data-source-ipeds':    '.claude/skills/education-data-source-ipeds/SKILL.md',
        'education-data-source-fsa':      '.claude/skills/education-data-source-fsa/SKILL.md',
        'education-data-source-scorecard':'.claude/skills/education-data-source-scorecard/SKILL.md',
        'data-scientist':                 '.claude/skills/data-scientist/SKILL.md',
        'daaf-orchestrator':              '.claude/skills/daaf-orchestrator/SKILL.md',
        'polars':                         '.claude/skills/polars/SKILL.md',
        'plotnine':                       '.claude/skills/plotnine/SKILL.md',
        'statsmodels':                    '.claude/skills/statsmodels/SKILL.md',
        'science-communication':          '.claude/skills/science-communication/SKILL.md',
        'marimo':                         '.claude/skills/marimo/SKILL.md',
    };

    // §§ FILE_DESCRIPTIONS (per-file plain-language explanations) ======
    // Powers the right column of the Read More "Files Referenced" /
    // "Files Produced" rows. (f version) Keys are full repo paths for
    // unambiguous lookup — every file referenced in PIPELINE_STEPS has
    // exactly one entry here. describeFile() tries path-keyed lookup
    // first, then falls back to basename/kind heuristics for anything
    // added later that is not yet in this map.
    //
    // Pattern (set by the subagent that drafted this map): every
    // description is a single sentence, ≤25 words, active voice,
    // present tense, beginning with a noun phrase that names the file
    // type ("A Skill file that…", "An agent file that defines…",
    // "A Python script that…", "The Plan document that…").
    // ================================================================
    const FILE_DESCRIPTIONS = {
        // —— Project root ————————————————————————————————————
        'CLAUDE.md': 'A base set of guiding principles and practices that aligns how every assistant in the DAAF system works.',
        // —— Skills (12) ——————————————————————————————————————
        '.claude/skills/daaf-orchestrator/SKILL.md': "A Skill file that teaches Claude how to navigate and manage workflows for DAAF projects. It defines behavioral protocols like rules for engaging with the researcher, how to delegate work, core operating procedures, subagent dispatch patterns, and the session-recovery contract that lets work resume after interruptions.",
        '.claude/skills/data-scientist/SKILL.md': 'A Skill file that teaches Claude rigorous data science best practices and methodology, spanning exploratory analysis, validation, statistical modeling, causal inference, and visualization design.',
        '.claude/skills/education-data-context/SKILL.md': 'A Skill file that teaches Claude how to interpret coded values (like -1 meaning "missing"), year definitions, and other source-specific quirks in U.S. education datasets.',
        '.claude/skills/education-data-explorer/SKILL.md': 'A Skill file that teaches Claude how to discover and map education datasets from the Urban Institute portal, locating relevant endpoints, variables, and year coverage for research planning.',
        '.claude/skills/education-data-query/SKILL.md': 'A Skill file that teaches Claude how to download education datasets from configured mirror sources as Parquet or CSV and filter them locally with Polars.',
        '.claude/skills/education-data-source-fsa/SKILL.md': 'A Skill file that teaches Claude how to access and interpret Federal Student Aid (FSA) institutional data covering Pell Grants, federal loans, and Title IV financial-aid metrics.',
        '.claude/skills/education-data-source-ipeds/SKILL.md': 'A Skill file that teaches Claude how to use IPEDS: the federal higher-education survey that covers enrollment, completions, graduation rates, finance, and financial aid for roughly 6,500 U.S. colleges and universities.',
        '.claude/skills/education-data-source-scorecard/SKILL.md': 'A Skill file that teaches Claude how to use the College Scorecard, a federal dataset that links student-aid records to IRS earnings data so it can report what graduates actually earn after college.',
        '.claude/skills/plotnine/SKILL.md': 'A Skill file that teaches Claude best practices for plotnine, the Python grammar-of-graphics library used to produce publication-quality charts in this project.',
        '.claude/skills/polars/SKILL.md': 'A Skill file that teaches Claude best practices for Polars, the fast dataframe library used for all data cleaning, joining, and analysis in this project.',
        '.claude/skills/science-communication/SKILL.md': 'A Skill file that teaches Claude how to translate technical findings into plain language for stakeholder reports, policy briefs, and other non-specialist audiences.',
        '.claude/skills/statsmodels/SKILL.md': 'A Skill file that teaches Claude best practices for statsmodels, the Python library used for regression modeling and statistical inference in this project.',
        '.claude/skills/marimo/SKILL.md': 'A Skill file that teaches Claude best practices for Marimo, the Python reactive-notebook library used to assemble the reproducible walkthrough at the end of every DAAF project.',

        // —— Skill references (36) ————————————————————————————
        '.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md': 'A reference inside the daaf-orchestrator Skill that walks Claude through running a research project end-to-end from a fresh prompt through final report.',
        '.claude/skills/daaf-orchestrator/references/revision-and-extension-mode.md': 'A reference inside the daaf-orchestrator Skill that walks Claude through revising or extending a completed research project without restarting from scratch.',
        '.claude/skills/daaf-orchestrator/references/session-recovery.md': 'A reference inside the daaf-orchestrator Skill that walks Claude through resuming an interrupted research project by reading the STATE file and picking up where prior work left off.',
        '.claude/skills/data-scientist/references/descriptive-analysis.md': 'A reference inside the data-scientist Skill that walks Claude through descriptive analysis: summary statistics, distributions, and group comparisons that precede modeling.',
        '.claude/skills/data-scientist/references/statistical-modeling.md': 'A reference inside the data-scientist Skill that walks Claude through choosing, fitting, and interpreting statistical models for research questions.',
        '.claude/skills/data-scientist/references/visualization-design.md': 'A reference inside the data-scientist Skill that walks Claude through designing effective charts: choosing the right encodings for the question being asked.',
        '.claude/skills/data-scientist/references/visualization-execution.md': 'A reference inside the data-scientist Skill that walks Claude through executing the chart design in code: turning a planned visualization into rendered output.',
        '.claude/skills/education-data-context/references/ipeds-context.md': 'A reference inside the education-data-context Skill that documents IPEDS-specific quirks Claude needs to know: coded categories, missingness conventions, and year alignment.',
        '.claude/skills/education-data-explorer/references/colleges-endpoints.md': 'A reference inside the education-data-explorer Skill that catalogs the Urban Institute portal endpoints covering postsecondary (college-level) data.',
        '.claude/skills/education-data-query/references/datasets-reference.md': 'A reference inside the education-data-query Skill that catalogs the available education datasets, what each contains, and when to reach for it.',
        '.claude/skills/education-data-query/references/fetch-patterns.md': 'A reference inside the education-data-query Skill that shows Claude the standard code patterns for fetching, filtering, and caching education datasets locally.',
        '.claude/skills/education-data-query/references/mirrors.yaml': 'A reference file inside the education-data-query Skill that lists the mirror URLs Claude uses to download Parquet and CSV copies of each education dataset.',
        '.claude/skills/education-data-source-fsa/references/data-quality.md': 'A reference inside the education-data-source-fsa Skill that flags known data-quality issues in Federal Student Aid records: suppressed cells, schema breaks, and reporting gaps.',
        '.claude/skills/education-data-source-fsa/references/title-iv-programs.md': 'A reference inside the education-data-source-fsa Skill that explains the Title IV federal aid programs (Pell, Direct Loans, PLUS, campus-based aid) covered by the data.',
        '.claude/skills/education-data-source-fsa/references/variable-definitions.md': 'A reference inside the education-data-source-fsa Skill that defines each variable in the FSA data tables: what it measures, how it is coded, and unit of observation.',
        '.claude/skills/education-data-source-ipeds/references/data-quality.md': 'A reference inside the education-data-source-ipeds Skill that flags known IPEDS data-quality issues: imputation flags, suppressed values, and survey-component coverage gaps.',
        '.claude/skills/education-data-source-ipeds/references/enrollment-data.md': 'A reference inside the education-data-source-ipeds Skill that explains the IPEDS enrollment survey components: fall enrollment, 12-month headcount, and demographic breakdowns.',
        '.claude/skills/education-data-source-ipeds/references/finance-data.md': 'A reference inside the education-data-source-ipeds Skill that explains the IPEDS finance survey: institutional revenue, expenditure, and asset reporting by sector.',
        '.claude/skills/education-data-source-ipeds/references/financial-aid.md': 'A reference inside the education-data-source-ipeds Skill that explains the IPEDS Student Financial Aid component: grant aid, loans, and net price by institution.',
        '.claude/skills/education-data-source-ipeds/references/graduation-rates.md': 'A reference inside the education-data-source-ipeds Skill that explains how IPEDS computes graduation rates: the cohort definition, time-to-degree windows, and demographic subgroups.',
        '.claude/skills/education-data-source-ipeds/references/institution-identifiers.md': 'A reference inside the education-data-source-ipeds Skill that explains UNITID and the other institution identifiers used to join IPEDS tables to other federal datasets.',
        '.claude/skills/education-data-source-ipeds/references/survey-components.md': 'A reference inside the education-data-source-ipeds Skill that maps out the full set of IPEDS survey components and which research questions each one supports.',
        '.claude/skills/education-data-source-scorecard/references/completion-rates.md': 'A reference inside the education-data-source-scorecard Skill that explains the College Scorecard completion-rate variables and how they differ from the IPEDS graduation-rate methodology.',
        '.claude/skills/education-data-source-scorecard/references/data-quality.md': 'A reference inside the education-data-source-scorecard Skill that flags Scorecard data-quality issues: privacy suppression, sample-size thresholds, and Title-IV-only coverage caveats.',
        '.claude/skills/education-data-source-scorecard/references/debt-repayment.md': 'A reference inside the education-data-source-scorecard Skill that explains the Scorecard student-debt and loan-repayment variables and how they are constructed.',
        '.claude/skills/education-data-source-scorecard/references/earnings-data.md': 'A reference inside the education-data-source-scorecard Skill that explains the Scorecard post-enrollment earnings variables, which are constructed by linking federal aid records to IRS tax records.',
        '.claude/skills/education-data-source-scorecard/references/population-coverage.md': 'A reference inside the education-data-source-scorecard Skill that explains who is represented in Scorecard outcomes (only students who received federal financial aid) and the selection bias that creates.',
        '.claude/skills/education-data-source-scorecard/references/variable-definitions.md': 'A reference inside the education-data-source-scorecard Skill that defines each Scorecard variable, its coding, units, and reporting cohort.',
        '.claude/skills/plotnine/references/aesthetics.md': 'A reference inside the plotnine Skill that walks Claude through plotnine aesthetic mappings: how data columns are bound to visual properties like color, shape, and size.',
        '.claude/skills/plotnine/references/facets-themes.md': 'A reference inside the plotnine Skill that walks Claude through plotnine facets and themes for multi-panel layouts and styling.',
        '.claude/skills/plotnine/references/geoms.md': 'A reference inside the plotnine Skill that walks Claude through the plotnine geom layer reference: points, bars, lines, smooths, and the other plot primitives.',
        '.claude/skills/plotnine/references/gotchas.md': 'A reference inside the plotnine Skill that flags common plotnine pitfalls and surprising behaviors Claude should avoid.',
        '.claude/skills/plotnine/references/scales-coords.md': 'A reference inside the plotnine Skill that walks Claude through plotnine scales and coordinate systems: controlling axes, legends, and transformations.',
        '.claude/skills/science-communication/references/plain-language.md': 'A reference inside the science-communication Skill that teaches Claude plain-language writing techniques for translating technical findings to non-specialist readers.',
        '.claude/skills/statsmodels/references/diagnostics.md': 'A reference inside the statsmodels Skill that walks Claude through regression diagnostics: checking residuals, leverage, multicollinearity, and model assumptions.',
        '.claude/skills/statsmodels/references/linear-models.md': 'A reference inside the statsmodels Skill that walks Claude through fitting and interpreting linear regression models in statsmodels.',

        // —— Agents (11) ————————————————————————————————————————
        // File-as-artifact descriptions: what the file contains and how
        // it is used in the dispatch process. Deliberately different from
        // AGENT_DESCRIPTIONS (which describes what the agent type DOES)
        // so the card header and the spec-file row never show duplicate text.
        '.claude/agents/search-agent.md': 'The core behavioral instructions for the search specialist assistant. It defines the read-only search strategy, the structured-return format, and the stop conditions that keep the search focused.',
        '.claude/agents/source-researcher.md': 'The core behavioral instructions for the source-research specialist assistant. It specifies how to investigate a single data source: what to catalog, what caveats to surface, and the structured report template for returning findings.',
        '.claude/agents/data-planner.md': 'The core behavioral instructions for the analytic planning specialist assistant. It contains the Plan and Plan_Tasks templates, the gate conditions the plan must satisfy, and the self-check rubric the planner runs before returning.',
        '.claude/agents/plan-checker.md': 'The core behavioral instructions for the adversarial analytic plan reviewer specialist assistant. It defines the six-dimension verification framework, the severity classification scheme, and the override rules for autonomous deviations.',
        '.claude/agents/research-executor.md': "The core behavioral instructions for the analytic coding specialist assistant. It defines the inline audit trail standard, the execution-and-capture workflow, the commit conventions, and the structured return format for every script task.",
        '.claude/agents/code-reviewer.md': 'The core behavioral instructions for the adversarial code reviewer specialist assistant. It mandates writing a separate diagnostic script (never editing the original), the 5+5 default check suite, and the severity-tagged findings format.',
        '.claude/agents/report-writer.md': "The core behavioral instructions for the report-drafting specialist assistant. It contains the stakeholder report template, the citation and AI-disclosure conventions, and the 10-point self-check the writer runs before returning.",
        '.claude/agents/data-verifier.md': 'The core behavioral instructions for the final report verification specialist assistant. It defines the six-check adversarial protocol including the Telephone Game trace, the severity classification, and the structured findings return format.',
        '.claude/agents/notebook-assembler.md': 'The core behavioral instructions for the reproducible analytic notebook compiler specialist assistant. It enforces the "compiler not analyst" rule: read each script verbatim, copy it into a Marimo notebook cell, and never add original analysis.',
        '.claude/agents/research-synthesizer.md': 'The core behavioral instructions for the data source research consolidation specialist assistant. It defines the structured synthesis template for merging parallel investigation reports into a single coherent narrative.',
        '.claude/agents/debugger.md': 'The core behavioral instructions for the intensive code debugging specialist assistant. It defines the diagnostic workflow: reproduce the error, identify root cause, apply a minimal fix, and verify the fix resolves the issue.',

        // —— Workflow references (14) ————————————————————————
        'agent_reference/AI_DISCLOSURE_REFERENCE.md': 'A workflow reference document that tells Claude how to disclose AI involvement in research outputs: what to attribute, where, and in what language.',
        'agent_reference/CITATION_REFERENCE.md': 'A workflow reference document that lays out the citation conventions Claude follows when referencing data sources, prior work, and external evidence in research deliverables.',
        'agent_reference/INLINE_AUDIT_TRAIL.md': 'A workflow reference that teaches Claude to embed inline comments in every script, explaining the intent, reasoning, and assumptions behind each data operation so a human reviewer can audit the work.',
        'agent_reference/PLAN_TASKS_TEMPLATE.md': 'A workflow template document that provides the canonical structure for the Plan_Tasks file, the granular task list derived from the research plan.',
        'agent_reference/PLAN_TEMPLATE.md': 'A workflow template document that provides the canonical structure for the research Plan: question, methodology, data sources, and analytical approach.',
        'agent_reference/REPORT_TEMPLATE.md': 'A workflow template document that provides the canonical structure for the final stakeholder Report drafted at the end of a project.',
        'agent_reference/SCRIPT_EXECUTION_REFERENCE.md': 'A workflow reference document that walks Claude through how to run, log, and validate analysis scripts during the execution phase.',
        'agent_reference/STATE_TEMPLATE.md': 'A workflow template document that provides the canonical structure for the STATE file Claude writes after every step to enable session recovery.',
        'agent_reference/VALIDATION_CHECKPOINTS.md': 'A workflow reference that lists the mandatory validation checkpoints Claude must clear at each phase: hard gates that stop the pipeline if data is empty, broken, or unexpectedly transformed.',
        'agent_reference/WORKFLOW_PHASE1_DISCOVERY.md': 'A workflow reference document that walks Claude through the specific details of the Discovery Phase of the pipeline: scoping the research question and discovering candidate data sources.',
        'agent_reference/WORKFLOW_PHASE2_PLANNING.md': 'A workflow reference document that walks Claude through the specific details of the Planning Phase of the pipeline: drafting and adversarially reviewing the formal analysis plan.',
        'agent_reference/WORKFLOW_PHASE3_ACQUISITION.md': 'A workflow reference document that walks Claude through the specific details of the Data Acquisition Phase of the pipeline: fetching raw data, cleaning it, and preparing it for analysis.',
        'agent_reference/WORKFLOW_PHASE4_ANALYSIS.md': 'A workflow reference document that walks Claude through the specific details of the Analysis Phase of the pipeline: running the planned statistical analyses and validating the results.',
        'agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md': 'A workflow reference document that walks Claude through the specific details of the Synthesis Phase of the pipeline: synthesizing findings into a final report and reproducible notebook.',

        // —— Project deliverables (6) ————————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py': 'The reproducible Marimo notebook, a browseable walkthrough of the whole selectivity-vs-graduation-rate analysis, assembled from the scripts that actually ran so what you see is exactly what was executed.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md': 'The Plan document that lays out the research question, methodology, data sources, and analytical approach for the entire selectivity-vs-graduation-rate study.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md': 'Machine-readable task sequence: 33 data operations in total. Every task has explicit file paths, skill bindings, and a verifiable completion conditions tied to a checkpoint gate, so execution cannot drift from the plan silently.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md': 'The final Report that presents the selectivity-vs-graduation-rate findings to stakeholders in plain language, with figures, caveats, and key takeaways.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md': 'The LEARNINGS file that captures methodological insights, surprises, and process notes from the project for reuse on future research.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md': "The STATE file: a running session log the orchestrator updates after every step, so if the session is interrupted (network drop, context exhaustion, user close) work can pick up right where it left off.",

        // —— Data files (4) ————————————————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_analysis.parquet': 'A Parquet data file holding the final analysis-ready dataset, one row per college, with every variable used in the statistical models. This is what every regression and figure reads from.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_core.parquet': 'A Parquet data table that holds the core institution-level variables (identifiers, sector, admission rate, graduation rate) before demographic enrichment.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_core_demographics.parquet': 'A Parquet data table that holds the core institution variables joined with student demographic characteristics (Pell share, underrepresented minority share).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_merged.parquet': 'A Parquet data file holding every variable from IPEDS, Scorecard, and FSA joined together on UNITID (the federal college ID), the raw material from which the analysis sample is filtered.',

        // —— Analysis outputs (7) ————————————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_correlation_matrix.parquet': 'A Parquet analysis output that holds the pairwise correlation matrix among the institution-level features used in the study.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_crosstab_selectivity_pell.parquet': 'A Parquet analysis output that holds the cross-tabulation of admission selectivity tiers against Pell-recipient share buckets.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_crosstab_selectivity_urm.parquet': 'A Parquet analysis output that holds the cross-tabulation of admission selectivity tiers against underrepresented-minority enrollment share.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_descriptive_by_selectivity.parquet': 'A Parquet analysis output that holds descriptive statistics (means, medians, dispersion) for every key variable broken out by selectivity tier.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_outperformers.parquet': 'A Parquet analysis output listing the colleges whose actual graduation rate substantially exceeds what the regression model would predict from their selectivity and demographics: the "outperformers" list.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_regression_results.parquet': 'A Parquet analysis output holding the regression results (coefficients, standard errors, and fit statistics) for the graduation-rate models. This is the statistical backbone of the report.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_sector_comparison.parquet': 'A Parquet analysis output that holds the side-by-side comparison of graduation-rate patterns across institutional sectors (public, private nonprofit, for-profit).',

        // —— Figures (6) ————————————————————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_actual_vs_predicted.png': "Figure 4: each college's actual graduation rate plotted against what the regression model predicted for it. Colleges above the diagonal graduate more students than their selectivity alone would suggest.",
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png': 'Figure 1: side-by-side boxplots showing the distribution of graduation rates within each admission selectivity tier. The lead descriptive visualization for the whole study.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_correlation_heatmap.png': 'Figure 6: a color-coded heatmap visualizing the correlation matrix among institution-level features.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png': 'Figure 2: graduation rate plotted against admission rate across institutions, showing the headline relationship at the heart of the study.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png': 'Figure 3: a heatmap of graduation rates across the joint grid of admission selectivity and Pell-recipient share.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_sector_comparison.png': 'Figure 5: graduation-rate distributions compared across institutional sectors (public, private nonprofit, for-profit).',

        // —— Logs directory (1) ————————————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/': 'A directory holding the full text transcripts of every Claude Code session that touched this project: the audit trail for exactly what was said, asked, and decided during the work.',

        // —— Output directories (2) ————————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/': 'A directory holding the analysis-output Parquet files (regression results, correlation matrix, crosstabs, descriptives, outperformer list) that the report draws every numerical claim from.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/': 'A directory holding the six PNG figures the analysis produced, ready for embedding in the final report and the Marimo walkthrough notebook.',

        // —— Python scripts — stage5_fetch (14) ——————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py': 'A Python script that fetches the IPEDS (federal higher-education survey) institutional directory, the master list of colleges the whole analysis is anchored to.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py': 'A Python script that fetches IPEDS admissions data including applicant counts, admit counts, and enrollee counts used to derive admit rates.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates.py': 'A Python script that fetches IPEDS graduation-rate data tracking first-time full-time bachelor-seeking cohort outcomes at the institution level.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates_a.py': 'First revision (`_a`) of `03_fetch-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py': 'A Python script that fetches Federal Student Aid (FSA) Pell Grant recipient counts by institution from the federal aid program data files.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_a.py': 'First revision (`_a`) of `04_fetch-fsa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_b.py': 'Second revision (`_b`) of `04_fetch-fsa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py': 'Third revision (`_c`) of `04_fetch-fsa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_d.py': 'Fourth revision (`_d`) of `04_fetch-fsa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/05_fetch-enrollment-race.py': 'A Python script that fetches IPEDS enrollment counts broken out by race and ethnicity for downstream demographic analysis.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/06_fetch-sfr.py': 'A Python script that fetches IPEDS student-to-faculty ratio data as one of the institutional resource indicators.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/07_fetch-retention.py': 'A Python script that fetches IPEDS first-year retention rate data for full-time bachelor-seeking students.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/08_fetch-finance.py': 'A Python script that fetches IPEDS institutional finance data covering expenses per FTE student and core revenue categories.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/09_fetch-sfa-grants.py': 'A Python script that fetches IPEDS Student Financial Aid grant and award data as a cross-reference to the FSA Pell figures.',

        // —— Python scripts — stage6_clean (11) ——————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/01_clean-directory.py': 'A Python script that cleans the institutional directory, filtering to four-year degree-granting Title IV institutions used throughout the analysis.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/02_clean-admissions.py': 'A Python script that cleans the admissions data, computing admit rates and restricting to years where every institution reported a complete cohort.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates.py': 'A Python script that cleans the graduation-rate data, deriving a consistent first-time full-time cohort completion rate per institution.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_a.py': 'First revision (`_a`) of `03_clean-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_b.py': 'Second revision (`_b`) of `03_clean-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_c.py': 'Third revision (`_c`) of `03_clean-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/04_clean-sfa-grants.py': 'A Python script that cleans the IPEDS Student Financial Aid grants data, normalizing award fields for cross-reference with FSA totals.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py': 'A Python script that cleans the race/ethnicity enrollment data and computes each institution\'s underrepresented-minority (URM) enrollment share.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/06_clean-sfr.py': 'A Python script that cleans student-to-faculty ratios, handling outliers and excluding specialized institutions where the ratio is not meaningful.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/07_clean-retention.py': 'A Python script that cleans first-year retention-rate data, filtering implausible values and aligning the cohort definition across years.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/08_clean-finance.py': 'A Python script that cleans institutional finance data and computes instructional expenditure per full-time-equivalent (FTE) student.',

        // —— Python scripts — stage7_transform (5) ——————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/01_join-core.py': 'A Python script that joins the cleaned directory with admissions and graduation rates to form the core institution-level analysis table.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/02_join-demographics.py': 'A Python script that joins student-demographic variables (race/ethnicity composition and Pell-recipient share) onto the core analysis table.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/03_join-resources.py': 'A Python script that joins institutional-resource variables (finance, faculty ratio, and retention) onto the core analysis table.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands.py': 'A Python script that creates the four selectivity bands (Highly Selective, Selective, Moderately Selective, Open/Less Selective) from admit-rate cutoffs.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands_a.py': 'First revision (`_a`) of `04_create-bands.py`.',

        // —— Python scripts — stage8_analysis (28) —————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py': 'A Python script that computes descriptive statistics of graduation rates within each selectivity band: means, medians, and spread.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell.py': 'A Python script that builds a cross-tabulation of average graduation rates by selectivity band and Pell-share quintile.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell_a.py': 'First revision (`_a`) of `02_crosstab-selectivity-pell.py`. Renamed the index column before unpivoting to sidestep a polars column-name collision.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm.py': 'A Python script that builds a cross-tabulation of average graduation rates by selectivity band and underrepresented-minority (URM) share quintile.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm_a.py': 'First revision (`_a`) of `03_crosstab-selectivity-urm.py`. Hit the same polars unpivot column-collision as the Pell crosstab and was fixed the same way.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix.py': 'A Python script that computes the correlation matrix among all key institutional variables: selectivity, demographics, resources, and outcomes.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix_a.py': 'First revision (`_a`) of `04_correlation-matrix.py`. Renamed the variable column before unpivoting to avoid the same polars collision that tripped the crosstabs.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/05_outperformers.py': 'A Python script that identifies institutions whose graduation rates exceed what their selectivity alone would predict: the headline outperformer list.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py': 'A Python script that fits a stepped series of regression models, starting with selectivity alone, then layering in demographics, then institutional resources, to see how much each set of factors explains graduation rates.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py': 'A Python script that compares the selectivity-graduation relationship separately for public, private nonprofit, and for-profit colleges, which is where the story gets most interesting.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/08_viz-scatter-grad-admit.py': 'A Python script that produces the scatter plot of graduation rate versus admission rate (Figure 2) with a fitted trend line.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity.py': 'A Python script that produces the boxplot of graduation rates by selectivity band (Figure 1), the lead descriptive visualization.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_a.py': 'First revision (`_a`) of `09_viz-boxplot-selectivity.py` (Figure 1). Fixed the plotnine `stat_summary` call that was passing a callable where a string function name was required.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_b.py': 'Second revision (`_b`) of `09_viz-boxplot-selectivity.py` (Figure 1). Replaced the R-style color names that plotnine\'s mizani dependency could not resolve.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py': 'A Python script that produces the heatmap of graduation rates by selectivity band and Pell-share quintile (Figure 3).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_a.py': 'First revision (`_a`) of `10_viz-heatmap-selectivity-pell.py` (Figure 3). Fixed the column-name `n` vs `N` mismatch that broke the heatmap pivot.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_b.py': 'Second revision (`_b`) of `10_viz-heatmap-selectivity-pell.py` (Figure 3). Removed the deprecated `guide_colorbar(barwidth=)` argument that plotnine no longer accepts.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_c.py': 'Third revision (`_c`) of `10_viz-heatmap-selectivity-pell.py` (Figure 3). Replaced the unrecognized `guide=False` argument with the modern plotnine equivalent and finally landed.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap.py': 'A Python script that produces the correlation-matrix heatmap (Figure 6) visualizing pairwise relationships among institutional variables.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap_a.py': 'First revision (`_a`) of `11_viz-correlation-heatmap.py` (Figure 6). Renamed the index column before the polars unpivot to fix the same DuplicateError that hit the earlier crosstabs.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison.py': 'A Python script that produces the sector-comparison scatter plot (Figure 5) contrasting Public, Private NP, and For-Profit institutions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison_a.py': 'First revision (`_a`) of `12_viz-sector-comparison.py` (Figure 5). Removed the plotnine `guide=False` argument that the newer API no longer recognizes.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison_c.py': 'Third revision (`_c`) of `12_viz-sector-comparison.py` (Figure 5). Note that `_b` does not appear; that attempt was abandoned and the revision chain jumped ahead.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison_d.py': 'Fourth revision (`_d`) of `12_viz-sector-comparison.py` (Figure 5).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter.py': 'A Python script that produces the actual-versus-predicted scatter (Figure 4) highlighting institutions that outperform the selectivity-only regression.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter_a.py': 'First revision (`_a`) of `13_viz-residual-scatter.py` (Figure 4).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter_b.py': 'Second revision (`_b`) of `13_viz-residual-scatter.py` (Figure 4).',

        // —— Python scripts — cr/ code-review memos (42) ——————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr1.py': 'The first code-review script in this project. The code-reviewer agent writes its own diagnostic script (never editing the original) to independently verify `01_fetch-directory.py`. Later `cr2`, `cr3` scripts repeat this for revised versions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr2.py': 'Code-review round 2 of `01_fetch-directory.py`, after the first round of fixes. Round 2 reviews the revised script to confirm the fix actually did what it promised, which is why some scripts accumulate multiple review rounds while simpler ones stop at round 1.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_02_cr1.py': 'Code-review round 1 of `02_fetch-admissions.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr1.py': 'Code-review round 1 of `03_fetch-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr2.py': 'Code-review round 2 of `03_fetch-grad-rates.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_04_cr1.py': 'Code-review round 1 of `04_fetch-fsa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_05_cr1.py': 'Code-review round 1 of `05_fetch-enrollment-race.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_06_cr1.py': 'Code-review round 1 of `06_fetch-sfr.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_07_cr1.py': 'Code-review round 1 of `07_fetch-retention.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_08_cr1.py': 'Code-review round 1 of `08_fetch-finance.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr1.py': 'Code-review round 1 of `09_fetch-sfa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr2.py': 'Code-review round 2 of `09_fetch-sfa-grants.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_01_cr1.py': 'Code-review round 1 of `01_clean-directory.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_02_cr1.py': 'Code-review round 1 of `02_clean-admissions.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_03_cr1.py': 'Code-review round 1 of `03_clean-grad-rates.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr1.py': 'Code-review round 1 of `04_clean-sfa-grants.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr2.py': 'Code-review round 2 of `04_clean-sfa-grants.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py': 'Code-review round 1 of `05_clean-enrollment-race.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_06_cr1.py': 'Code-review round 1 of `06_clean-sfr.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr1.py': 'Code-review round 1 of `07_clean-retention.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr2.py': 'Code-review round 2 of `07_clean-retention.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr1.py': 'Code-review round 1 of `08_clean-finance.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr2.py': 'Code-review round 2 of `08_clean-finance.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr1.py': 'Code-review round 1 of `01_join-core.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr2.py': 'Code-review round 2 of `01_join-core.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1.py': 'Code-review round 1 of `02_join-demographics.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1_a.py': "A revised version of `stage7_02_cr1.py` itself. Rare, but sometimes the code-review script needs its own fix before it can finish auditing its target, so the auditors can need revision too.",
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr1.py': 'Code-review round 1 of `03_join-resources.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr2.py': 'Code-review round 2 of `03_join-resources.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py': 'Code-review round 1 of `04_create-bands.py`.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr2.py': 'Code-review round 2 of `04_create-bands.py`, after initial revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_01_cra1.py': 'Code-review round a1 of `01_descriptive-by-selectivity.py`. The "a" suffix marks the analysis-track review (QA4a), distinct from the visualization-track reviews ("b") that come later.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_01_cra2.py': 'Code-review round a2 of `01_descriptive-by-selectivity.py`, after initial analysis-track revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_02_cra1.py': 'Code-review round a1 of `02_crosstab-selectivity-pell.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_03_cra1.py': 'Code-review round a1 of `03_crosstab-selectivity-urm.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_04_cra1.py': 'Code-review round a1 of `04_correlation-matrix.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_05_cra1.py': 'Code-review round a1 of `05_outperformers.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_06_cra1.py': 'Code-review round a1 of `06_regression-models.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra1.py': 'Code-review round a1 of `07_sector-comparison.py` (analysis track).',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra2.py': 'Code-review round a2 of `07_sector-comparison.py`, after initial analysis-track revisions.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_08_crb1.py': 'Code-review round b1 of `08_viz-scatter-grad-admit.py`. The "b" suffix marks the visualization-track review (QA4b), which focuses on chart clarity and misleading encodings instead of statistical correctness.',
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_13_crb1.py': 'Code-review round b1 of `13_viz-residual-scatter.py` (visualization track).',

        // —— Python scripts — top-level (2) —————————————————
        'research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/_build_notebook.py': 'A Python script that assembles the reproducible Marimo notebook by pulling every successful analysis script and its execution log into a single browseable walkthrough.',
        'scripts/run_with_capture.sh': "A DAAF-wide shell utility (framework-wide, not project-local) that runs any analysis script and captures stdout and stderr to an appended log block. Every Python script in every project is executed through this wrapper, which is how DAAF guarantees an audit trail.",
    };

    // §§ AGENT_DESCRIPTIONS (canonical per-type inline blurbs) ========
    // Single source of truth for the one-line "what this kind of
    // specialist is" text shown underneath the role header inside every
    // agent-flow card in the Read More. Keyed by `agentType`, the same
    // key used by AGENT_SPECS. buildAgentFlow() resolves the displayed
    // description from this map before falling back to the per-dispatch
    // `entry.agentDescription` string (kept as a vestigial fallback so
    // an unknown agentType still renders something sensible).
    //
    // Pattern (≤25 words, active voice, present tense, beginner-friendly):
    //   "The {name} specialist assistant, which …"
    // except for the orchestrator, which is the top-level session rather
    // than a dispatched specialist and so reads as a noun phrase.
    //
    // The step-specific nuance of what an agent did on a particular
    // dispatch lives in the `task` field on each agentFlow entry, NOT
    // here. This map is about the type, not the instance.
    // ================================================================
    const AGENT_DESCRIPTIONS = {
        'orchestrator':         "The DAAF orchestrator is the top-level Claude session that decides the next step, hands work off to specialist assistants, and pulls their findings together at every stage. Think of it as a lab manager.",
        'search-agent':         "The search-agent specialist assistant, which performs read-only exploratory searches across data sources, documentation, and the web to answer a focused question.",
        'source-researcher':    "The source-researcher specialist assistant, which deep-dives into a single data source to map its endpoints, variables, gotchas, and known limitations.",
        'data-planner':         "The data-planner specialist assistant, which takes everything learned during data exploration and turns it into a formal research Plan plus a machine-readable task list before any coding starts.",
        'plan-checker':         "The plan-checker specialist assistant, which stress-tests the research plan by actively looking for gaps, feasibility problems, and hidden assumptions before any code runs.",
        'research-executor':    "The research-executor specialist assistant, which writes, runs, and validates the Python scripts that fetch, clean, transform, and analyze the study's data.",
        'code-reviewer':        "The code-reviewer specialist assistant, which independently inspects every script the research-executor produces by running its own diagnostic code, never editing the original.",
        'report-writer':        "The report-writer specialist assistant, which drafts the final stakeholder report by grounding every claim in the project's analysis artifacts.",
        'data-verifier':        "The data-verifier specialist assistant, which skeptically re-checks every claim in the final report against the actual analysis outputs, as a last independent line of defense.",
        'notebook-assembler':   "The notebook-assembler specialist assistant, which packages the completed analysis scripts and logs into a reproducible Marimo notebook walkthrough.",
        'research-synthesizer': "The research-synthesizer specialist assistant, which consolidates findings from parallel investigations into one coherent narrative for the orchestrator.",
        'debugger':             "The debugger specialist assistant, which diagnoses and fixes script errors and unexpected results so the analysis can continue.",
    };

    // Verbatim user prompt, rendered into the original-prompt callout
    // above the dynamically fetched final report on the intro view.
    const USER_PROMPT = "I'm aware that graduation rates are often thought of as a key outcome for assessing a university/college's quality by the general public, but many researchers argue that there's a very strong question of chicken-or-the-egg in interpreting it that way: Are graduation rates high because the college actually did a good job in serving its students, or are graduation rates high because the college selectively admits students who are already highly competitive and academically prepared and likely to graduate/succeed anyway?\n\nI'd like to more critically explore this dynamic with data to better understand how correlated these things are, especially when thinking about additional complicating institutional factors like share of students on financial aid, other underserved or historically disadvantaged student population rates, etc. I'd like an analysis that helps provide an intuitive and holistic view on how these factors all relate to one another, and what implications that might have for broadly thinking about college 'quality' in general.";

    // §§ PIPELINE_STEPS ================================================
    // 20 entries: 16 steps + 4 checkpoints, rendered to both the left
    // panel and the progress rail. Each entry has:
    //   description         — orchestrator POV summary (always visible)
    //   orchestratorLogLine — { path, line } pointer into a real session
    //                         log, fetched and rendered in the right
    //                         panel when the card becomes active
    //   agentFlow           — ordered agent cards shown in Read More
    // PHASE_METADATA follows immediately after.
    // ================================================================
    const PIPELINE_STEPS =[
{
    id: "step-1",
    phase: 1,
    phaseName: "Discovery",
    title: "Understanding the Request",
    type: "step",
    timeHuman: "~2 min",
    timeClaude: "~30 sec",
    description: "The researcher tells Claude Code/DAAF in plain language what they want to analyze, which can be as specific and directed or broad and ambitious as they'd like. Because of the style and scale of the request, the DAAF orchestrator dynamically classifies this work as necessitating a full end-to-end analysis and loads the corresponding workflow instructions so it knows how to manage the work going forward. Before touching any data, it writes back a preliminary scoping confirmation to the user covering planned deliverables, likely data sources, geographic coverage, year range, and approximate record counts (the pre-flight checklist), then pauses and waits for the researcher's input. The researcher can narrow, broaden, or redirect DAAF's initial assessment of the work before anything else begins.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [6, 34]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Loaded the DAAF orchestrator skill, read the full pipeline workflow reference instructions, loaded the detailed Discovery Phase workflow reference, then wrote the pre-flight checklist message to the researcher and paused for confirmation before dispatching any specialist.",
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" },
          { name: "daaf-orchestrator", path: ".claude/skills/daaf-orchestrator/SKILL.md", kind: "skill", note: "DAAF workflow orchestration spec, loaded at session start" },
          { name: "full-pipeline-mode.md", path: ".claude/skills/daaf-orchestrator/references/full-pipeline-mode.md", kind: "reference", note: "Full pipeline reference (1,957 lines): exceeded the Read tool's 25k-token limit and had to be read in four offset/limit passes before the orchestrator could compose the pre-flight checklist" },
          { name: "WORKFLOW_PHASE1_DISCOVERY.md", path: "agent_reference/WORKFLOW_PHASE1_DISCOVERY.md", kind: "reference", note: "Discovery Phase pre-flight checklist template and dispatch guidance for the Searching for Data Sources and Deep-Diving into Each Data Source steps" },
        ],
        producedFiles: []
      }
    ]
  },

  {
    id: "step-2",
    phase: 1,
    phaseName: "Discovery",
    title: "Searching for Data Sources",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~5 min",
    description: "With the scope confirmed, the DAAF orchestrator delegates the next step of work to a search specialist assistant: a fresh and narrowly focused instance of Claude armed with DAAF's curated map of the federal postsecondary data landscape it has access to via the Urban Institute Education Data Portal. It surveys the three big data systems relevant here (IPEDS, Federal Student Aid, and College Scorecard), catalogues their data access processes, variable availability, and year coverage, and comes back with a structured inventory of candidate datasets (nine in total) covering every domain the question touches: graduation rates, admissions, enrollment demographics, financial aid, institutional finance, retention, and student-to-faculty ratio. Passing this work off to a specialist both enhances the quality and specificity of the searching and prevents the orchestrator from losing track of its own responsibilities and tasks for later on (an issue known as 'context rot').",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [38, 39]
    },
    agents: [
      {
        type: "search-agent",
        task: "Data Exploration",
        dispatch: 8,
        subagentId: "a6fc6821",
        toolCalls: 13,
        skills: ["education-data-explorer", "data-scientist"]
      }
    ],
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Wrote a structured dispatch prompt for the search specialist, giving it the verbatim research question from the researcher, explicit scope constraints, an output template, and the list of data-source families to investigate. It then reviewed the returned report from the specialist and flagged 10 specific items that needed deeper source-by-source follow-up before analytic planning could safely begin, to be conducted in the next step of work.",
        loadedFiles: [
          
          { name: "WORKFLOW_PHASE1_DISCOVERY.md", path: "agent_reference/WORKFLOW_PHASE1_DISCOVERY.md", kind: "reference", note: "Discovery Phase workflow reference: tells the orchestrator which search and source-research specialists to dispatch, what prompts to write them, and when to pause for the Discovery Phase checkpoint. The orchestrator deliberately does NOT load the data source skills itself; those get loaded inside each dispatched specialist, keeping the orchestrator's context lean." },
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a6fc6821.jsonl",
            line: 1,
            name: "Search-agent dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the search specialist — the full structured instructions it received as its starting context, including scope, constraints, and the output template."
          }
        ]
      },
      {
        role: "Search Specialist",
        agentType: "search-agent",
        task: "Loaded the education data explorer skills, surveyed all available federal postsecondary data systems catalogued in DAAF, and returned a structured inventory of candidate datasets across IPEDS, FSA, and College Scorecard, with key variables, year coverage, and a ranked list of items needing deeper investigation before the plan could be drafted.",
        dispatch: 8,
        subagentId: "a6fc6821",
        toolCalls: 13,
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" },
          { name: "data-scientist", path: ".claude/skills/data-scientist/SKILL.md", kind: "skill", note: "Rigorous data science methodology and mindset" },
          { name: "education-data-explorer", path: ".claude/skills/education-data-explorer/SKILL.md", kind: "skill", note: "Federal postsecondary data landscape reference" },
          { name: "colleges-endpoints.md", path: ".claude/skills/education-data-explorer/references/colleges-endpoints.md", kind: "reference", note: "College/university level endpoint catalogue" },
          { name: "education-data-source-ipeds SKILL.md", path: ".claude/skills/education-data-source-ipeds/SKILL.md", kind: "skill", note: "IPEDS source overview (scanned for context)" },
          { name: "education-data-source-fsa SKILL.md", path: ".claude/skills/education-data-source-fsa/SKILL.md", kind: "skill", note: "FSA source overview (scanned for context)" },
          { name: "education-data-source-scorecard SKILL.md", path: ".claude/skills/education-data-source-scorecard/SKILL.md", kind: "skill", note: "Scorecard source overview (scanned for context)" },
          { name: "datasets-reference.md", path: ".claude/skills/education-data-query/references/datasets-reference.md", kind: "reference", note: "Known dataset file paths for Education Data Portal mirrors" },
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a6fc6821.jsonl",
            line: 35,
            name: "Search specialist's final report",
            description: "The search specialist's structured search report back to the orchestrator: the candidate endpoint inventory and the list of items flagged for the parallel source deep-dives that follow. This is the handoff that determines what the next step's parallel deep-dive dispatches will investigate."
          }
        ]
      }
    ]
  },

  {
    id: "step-3",
    phase: 1,
    phaseName: "Discovery",
    title: "Deep-Diving into Each Data Source",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~5 min",
    description: "Based on the results from the high-level data source survey, the orchestrator starts up three additional search specialists focused on data documentation deep dives: one per data source, each loaded up with reference files providing deep expertise about its assigned data source. They work simultaneously in their own isolated silos: one combs through IPEDS's 12+ survey components for coded value mappings and the First-Time Full-Time student (FTFT) data coverage limitation, another traces exactly how to compute Pell share from Federal Student Aid recipient counts in the data, and the third investigates College Scorecard's year coverage and population sample biases. Each returns a structured report on their deep-dives to the orchestrator, and the insights articulate important data shape and interpretation nuances that are critical to performing good and thoughtful data analysis downstream.",
    // Multi-line render: shows the full thinking→speak→thinking→speak
    // arc of dispatching 3 parallel source researchers and reacting to
    // their returns. L42 is the orchestrator's internal reasoning about
    // what to investigate next; L43 is its outward message announcing
    // the dispatch; L50 is its internal reasoning after all three
    // researchers return; L51 is its outward summary of the findings.
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [42, 43]
    },
    agents: [
      { type: "source-researcher", task: "IPEDS deep-dive",    dispatch: 9,  subagentId: "a985f220", toolCalls: 16, skills: ["education-data-source-ipeds"] },
      { type: "source-researcher", task: "FSA deep-dive",      dispatch: 10, subagentId: "aeb9105a", toolCalls: 9,  skills: ["education-data-source-fsa"] },
      { type: "source-researcher", task: "Scorecard deep-dive",dispatch: 11, subagentId: "a0f86123", toolCalls: 9,  skills: ["education-data-source-scorecard"] },
    ],
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Wrote three separate dispatch prompts, one for IPEDS, one for FSA, one for Scorecard, each carrying the full research-question context, the source-specific list of questions flagged during the prior data source surveying step, and an explicit output template. Started all three dispatches in parallel, then reviewed each structured report as it returned and consolidated the findings for the next step.",
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a985f220.jsonl",
            line: 1,
            name: "IPEDS source-researcher dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the IPEDS source-researcher specialist."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_aeb9105a.jsonl",
            line: 1,
            name: "FSA source-researcher dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the FSA source-researcher specialist."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a0f86123.jsonl",
            line: 1,
            name: "Scorecard source-researcher dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the Scorecard source-researcher specialist."
          }
        ]
      },
      {
        role: "IPEDS Source Researcher",
        agentType: "source-researcher",
        task: "Investigated IPEDS-specific caveats across graduation rates, admissions, enrollment demographics, finance, retention, and student-faculty ratio, surfacing coded value mappings, suppression patterns, and the critical FTFT cohort limitation.",
        dispatch: 9,
        subagentId: "a985f220",
        toolCalls: 16,
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" },
          { name: "education-data-source-ipeds", path: ".claude/skills/education-data-source-ipeds/SKILL.md", kind: "skill", note: "IPEDS data source reference" },
          { name: "graduation-rates.md", path: ".claude/skills/education-data-source-ipeds/references/graduation-rates.md", kind: "reference", note: "GRS limitations and FTFT cohort definition" },
          { name: "enrollment-data.md", path: ".claude/skills/education-data-source-ipeds/references/enrollment-data.md", kind: "reference", note: "Race/ethnicity coding and URM computation" },
          { name: "finance-data.md", path: ".claude/skills/education-data-source-ipeds/references/finance-data.md", kind: "reference", note: "GASB vs FASB accounting differences" },
          { name: "survey-components.md", path: ".claude/skills/education-data-source-ipeds/references/survey-components.md", kind: "reference", note: "All 12+ IPEDS survey components" },
          { name: "data-quality.md", path: ".claude/skills/education-data-source-ipeds/references/data-quality.md", kind: "reference", note: "Finance data quality and cross-sector comparability issues" },
          { name: "financial-aid.md", path: ".claude/skills/education-data-source-ipeds/references/financial-aid.md", kind: "reference", note: "Student Financial Aid survey and net price data" },
          { name: "institution-identifiers.md", path: ".claude/skills/education-data-source-ipeds/references/institution-identifiers.md", kind: "reference", note: "UNITID and institution classification codes" },
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a985f220.jsonl",
            line: 42,
            name: "IPEDS source-researcher's final report",
            description: "The IPEDS source-researcher's final report: a source-specific caveats table, coded value mappings, suppression patterns, the GASB vs FASB finance comparability warning, and the FTFT cohort limitation the orchestrator will surface in the Discovery Phase checkpoint."
          }
        ]
      },
      {
        role: "FSA Source Researcher",
        agentType: "source-researcher",
        task: "Investigated FSA Grants data to determine how to correctly filter the data to Pell Grant recipients, clarified that FSA provides no enrollment denominator requiring a join to IPEDS undergrad enrollment, and confirmed year alignment with IPEDS.",
        dispatch: 10,
        subagentId: "aeb9105a",
        toolCalls: 9,
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" },
          { name: "education-data-source-fsa", path: ".claude/skills/education-data-source-fsa/SKILL.md", kind: "skill", note: "FSA data source reference: Title IV aid data" },
          { name: "variable-definitions.md", path: ".claude/skills/education-data-source-fsa/references/variable-definitions.md", kind: "reference", note: "Complete encoding tables for FSA categorical variables" },
          { name: "data-quality.md", path: ".claude/skills/education-data-source-fsa/references/data-quality.md", kind: "reference", note: "Coverage limitations, data lag, and known issues" },
          { name: "title-iv-programs.md", path: ".claude/skills/education-data-source-fsa/references/title-iv-programs.md", kind: "reference", note: "Title IV program definitions including Pell Grant specifics" },
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_aeb9105a.jsonl",
            line: 26,
            name: "FSA source-researcher's final report",
            description: "The FSA source-researcher's structured final report: the correct method for filtering Pell Grant recipients from other federal aid types, the confirmation that FSA has no enrollment denominator and must be joined to IPEDS undergraduate enrollment, and year alignment with IPEDS. In the orchestrator's log this return arrives before the IPEDS return even though IPEDS was dispatched first — parallel execution means returns land in completion order, not dispatch order."
          }
        ]
      },
      {
        role: "Scorecard Source Researcher",
        agentType: "source-researcher",
        task: "Investigated College Scorecard availability and discovered that key demographic variables (pct_pell, pct_black, pct_hispanic) are absent from Portal datasets, student data ends in 2016, and Scorecard's Title IV coverage bias directly correlates with the study's key predictor variable, recommending Scorecard be demoted to optional secondary use for earnings data only.",
        dispatch: 11,
        subagentId: "a0f86123",
        toolCalls: 9,
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" },
          { name: "education-data-source-scorecard", path: ".claude/skills/education-data-source-scorecard/SKILL.md", kind: "skill", note: "Scorecard data source reference: post-enrollment outcomes" },
          { name: "population-coverage.md", path: ".claude/skills/education-data-source-scorecard/references/population-coverage.md", kind: "reference", note: "Title IV-only coverage limitation and bias assessment" },
          { name: "variable-definitions.md", path: ".claude/skills/education-data-source-scorecard/references/variable-definitions.md", kind: "reference", note: "Scorecard variable naming and encoding conventions" },
          { name: "earnings-data.md", path: ".claude/skills/education-data-source-scorecard/references/earnings-data.md", kind: "reference", note: "Post-graduation earnings data structure and IRS link" },
          { name: "data-quality.md", path: ".claude/skills/education-data-source-scorecard/references/data-quality.md", kind: "reference", note: "Suppression patterns and data freshness issues" },
          { name: "completion-rates.md", path: ".claude/skills/education-data-source-scorecard/references/completion-rates.md", kind: "reference", note: "Scorecard completion rate methodology" },
          { name: "debt-repayment.md", path: ".claude/skills/education-data-source-scorecard/references/debt-repayment.md", kind: "reference", note: "Federal student debt and repayment outcome data" },
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a0f86123.jsonl",
            line: 25,
            name: "Scorecard source-researcher's final report",
            description: "The Scorecard source-researcher's final report: Scorecard's key demographic variables (pct_pell, pct_black, pct_hispanic) are NOT present in the Portal datasets, its student-characteristic data ends in 2016, and its Title IV coverage bias correlates directly with institutional selectivity, meaning using Scorecard would introduce systematic measurement error in the study's main independent variable."
          }
        ]
      }
    ]
  },

  {
    id: "step-4",
    phase: 1,
    phaseName: "Discovery",
    title: "Synthesizing Findings",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~5 min",
    description: "The orchestrator now has three in-depth data source reports: rich, structured, but not yet pulled together as a single picture for the purposes of informing an actual data analysis. Rather than stitch them together itself, the orchestrator dispatches one more specialist: a research synthesizer specialist whose only job is connecting the dots and thinking deeply about the nuances of several data sources in concert. The synthesizer reads all three reports, reconciles the conflicts/issues between them, designs a join strategy across IPEDS and FSA datasets based on unitid, and produces a single integrated data model: a unified variable mapping across nine analysis dimensions plus a consolidated 9-item limitations inventory. This is what the later analytical planning phase will use to build the actual data analysis methodology.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [50, 51]
    },
    agents: [
      { type: "research-synthesizer", task: "Findings Synthesis", dispatch: 12, subagentId: "af44dfd3", toolCalls: 0, skills: [] }
    ],
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Packaged the search-specialist inventory from the initial data source surveying step and all three source-researcher reports from the deep-dives step into a structured prompt to dispatch to the research-synthesizer, then used the returned synthesis report directly as the substantive content of the Discovery Phase checkpoint message that the Creating the Analysis Plan step presents to the researcher.",
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_af44dfd3.jsonl",
            line: 1,
            name: "Research-synthesizer dispatch prompt",
            description: "The prompt the DAAF Orchestrator wrote to launch the research-synthesizer. It carries the key points from all three source reports plus the search-specialist inventory from the Searching for Data Sources step as structured input."
          }
        ]
      },
      {
        role: "Research Synthesizer",
        agentType: "research-synthesizer",
        task: "Read all three source-researcher reports together, reconciled conflicts between them (e.g., which source should supply demographic variables, how to handle Scorecard's coverage bias), designed a strategy for linking records across IPEDS and FSA using their shared institution identifier, and produced a single integrated data model: a unified variable mapping and a consolidated limitations inventory that the later analytical planning phase will build on.",
        dispatch: 12,
        subagentId: "af44dfd3",
        toolCalls: 0,
        loadedFiles: [
          { name: "CLAUDE.md", path: "CLAUDE.md", kind: "reference" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_af44dfd3.jsonl",
            line: 3,
            name: "Research-synthesizer's unified data model",
            description: "The synthesizer's final report: (1) an inventory check confirming all three source reports were received, (2) the integrated data model naming IPEDS as primary with FSA for Pell counts and Scorecard formally demoted, (3) a conflict resolution log documenting key decisions and rationales, (4) a unified variable mapping covering all analysis dimensions, and (5) a consolidated limitations inventory for the risk register."
          }
        ]
      }
    ]
  },

  {
    id: "checkpoint-1",
    phase: 1,
    phaseName: "Discovery",
    title: "Are these the right data sources? Are they sufficient?",
    type: "checkpoint",
    timeHuman: "~5 min",
    timeClaude: "~0 sec",
    description: "After finishing the data discovery and investigation phase, the DAAF orchestrator reports back to the researcher with the synthesized key insights as related to the initial research question posed. This is the first of the pipeline's mandatory checkpoints to keep the human fully in the loop at all major decision points for their expertise and guidance. The researcher gets DAAF's informed assessment of what the data can and cannot do: which sources will be used, which constructs/variables are in play, which caveats matter, and other crucial considerations before proceeding to any actual analytic steps. For example, the College Scorecard data source, which looked perfectly promising at the outset, was demoted to optional secondary use because its sample coverage biases interfered with the core study concept of institutional selectivity. This is the kind of problem DAAF's in-depth data documentation discovery and synthesis process is specifically designed to catch and surface before proceeding, while allowing the human researcher to decide the best next steps for addressing and adapting the work accordingly.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: 55
    },
    reviewItems: [
      "Data sources identified (IPEDS primary, FSA for Pell counts, Scorecard demoted), with endpoints and year ranges",
      "Key variables and their availability across 9 analysis dimensions",
      "Source-specific caveats and limitations (9 items for the risk register)",
      "Suppression patterns and cross-sector comparability issues (GASB vs. FASB, FTFT cohort, race code changes)",
      "Feasibility assessment: ~1,500-2,500 four-year institutions with matching records across data sources for the target year 2020-2021",
      "Recommended approach: descriptive analysis by selectivity bins as primary story, hierarchical regression as supplementary evidence"
    ],
    researcherActions: [
      "Approve and move to planning",
      "Request more exploration of additional sources",
      "Adjust the scope of the research question",
      "Ask clarifying questions"
    ],
    purposeQuote: "I'm pausing here to make sure we've identified the right data and understand its limitations before investing time in methodology design."
  },
{
    id: "step-5",
    phase: 2,
    phaseName: "Planning",
    title: "Designing the Analytic Plan",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~30 min",
    description: "With discovery findings approved, the DAAF orchestrator hands off all the summarized data source insights and approved analytic specifications to a methodological planning specialist to translate everything it has learned into a formal, executable blueprint that the rest of the coding processes will follow. This is where the data analysis coding process actually gets designed: the research question gets locked in, methodological trade-offs get made, each data transformation gets spelled out, and the known risks that could break the analysis get named in advance. This planning specialist produces two companion files: the Plan is a strategic specification humans can read top-to-bottom (research question, key research outcomes, stated hypotheses, methodology rationale, data analysis design, and a concrete risk register). The Plan Tasks document is a machine-readable task sequence of 33 data/analytic operations to actually execute the Plan and get from raw data to analytic outputs: each with explicit input/output paths, join cardinalities, and verifiable 'done' conditions. This is the document that the orchestrator will eventually use to dispatch the coding specialist agents. The orchestrator also begins setting up the core project folder template so all work from here can be rigorously captured and recorded for full reproducibility/auditability going forward from this point on.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [59, 60, 75]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Read the Planning Phase workflow protocol, created the project folder skeleton, then composed the data-planner dispatch prompt with the user's original request copied verbatim plus all consolidated discovery findings from the Discovery Phase inlined. After the data-planner returned, it verified Plan.md and Plan_Tasks.md existed, then set up core workflow and project tracking files (STATE and LEARNINGS) for future agents to use.",
        loadedFiles: [
          
          {
            name: "WORKFLOW_PHASE2_PLANNING",
            path: "agent_reference/WORKFLOW_PHASE2_PLANNING.md",
            kind: "reference",
            note: "Protocol for the Creating the Analysis Plan and Automated Plan Validation steps: folder creation, planner invocation, gate conditions"
          },
          {
            name: "STATE_TEMPLATE",
            path: "agent_reference/STATE_TEMPLATE.md",
            kind: "reference",
            note: "Template for the session state tracking file that allows DAAF to persistently remember and track all the tasks to be done in the research project across multiple agents and sessions"
          }
        ],
        producedFiles: [
          {
            name: "STATE.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md",
            kind: "file",
            note: "The session state tracking file that allows DAAF to persistently remember and track all the tasks to be done in the research project across multiple agents and sessions. Note that this is a skeleton file that gets filled out progressively as the project proceeds; what you see here is the completed doc by project-end, but it begins basically empty."
          },
          {
            name: "LEARNINGS.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md",
            kind: "file",
            note: "The Lessons Learned tracking file that allows DAAF to track workflow, data source, and data analysis improvement opportunities for future work. Note that this is a skeleton file that gets filled out progressively as the project proceeds; what you see here is the completed doc by project-end, but it begins basically empty."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a88bd21a.jsonl",
            line: 1,
            name: "Orchestrator's data-planner dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the data-planner specialist."
          }
        ]
      },
      {
        role: "Analytic Planning Specialist",
        agentType: "data-planner",
        task: "Read the relevant planning templates and all relevant data source skills, then authored Plan.md and Plan_Tasks.md documents in full considering all insights and considerations together. Finished with a comprehensive self-check verifying every task has explicit paths, skills, done conditions, and no placeholders, before returning control to the orchestrator.",
        dispatch: 19,
        subagentId: "a88bd21a",
        toolCalls: 35,
        loadedFiles: [
          
          {
            name: "PLAN_TEMPLATE",
            path: "agent_reference/PLAN_TEMPLATE.md",
            kind: "reference",
            note: "Canonical structure the plan must follow: ensures every plan has the same sections (research outcomes, risk register, key decisions log) so human reviewers always know where to look"
          },
          {
            name: "PLAN_TASKS_TEMPLATE",
            path: "agent_reference/PLAN_TASKS_TEMPLATE.md",
            kind: "reference",
            note: "Canonical template for the machine-readable task sequence"
          },
          {
            name: "VALIDATION_CHECKPOINTS",
            path: "agent_reference/VALIDATION_CHECKPOINTS.md",
            kind: "reference",
            note: "Validation checkpoint definitions: each task in the plan must bind to one of these checkpoint gates in its 'done' condition, so execution cannot proceed past a silent failure"
          },
          {
            name: "SCRIPT_EXECUTION_REFERENCE",
            path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md",
            kind: "reference",
            note: "File-first protocol: guarantees every script written during execution will produce an appended execution log that a reviewer can audit without re-running code"
          },
          {
            name: "datasets-reference",
            path: ".claude/skills/education-data-query/references/datasets-reference.md",
            kind: "skill",
            note: "Known dataset file paths for all IPEDS and FSA endpoints"
          },
          {
            name: "mirrors.yaml",
            path: ".claude/skills/education-data-query/references/mirrors.yaml",
            kind: "skill",
            note: "Mirror URL patterns the planner used to confirm file paths exist for all 8 IPEDS endpoints before committing them to the plan"
          },
          {
            name: "education-data-source-ipeds",
            path: ".claude/skills/education-data-source-ipeds/SKILL.md",
            kind: "skill",
            note: "IPEDS coded value reference: tells the planner that -1=missing, -2=not applicable, -3=suppressed must never be treated as zero, plus the rule that URM excludes race codes 8 (nonresident alien) and 9 (unknown)"
          },
          {
            name: "education-data-source-fsa",
            path: ".claude/skills/education-data-source-fsa/SKILL.md",
            kind: "skill",
            note: "FSA Pell Grant reference: establishes that Pell share must be computed with IPEDS UG enrollment as the denominator, not the FSA count alone"
          }
        ],
        producedFiles: [
          {
            name: "Plan.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md",
            kind: "file",
            note: "Strategic analytic plan specification covering the research question, methodology, the 9-dataset data design, data transformation sequence, risk register, and output specs. This file is the analysis's audit trail: anyone who ever needs to understand how a finding was derived can trace the full chain of reasoning back to this document."
          },
          {
            name: "Plan_Tasks.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md",
            kind: "file",
            note: "Machine-readable task sequence: 33 data operations in total. Every task has explicit file paths, skill bindings, and a verifiable 'done' condition tied to a checkpoint gate, so execution cannot drift from the plan silently."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a88bd21a.jsonl",
            line: 90,
            name: "Data-planner's self-check and final report",
            description: "Before handing the plan back to the orchestrator, the planner walks its own checklist for plan completeness and consistency and then summarizes the general output of the plan for the orchestrator to review."
          }
        ]
      }
    ]
  },

  {
    id: "step-6",
    phase: 2,
    phaseName: "Planning",
    title: "Adversarial Plan Review",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~15 min",
    description: "Before sharing the drafted Plan with the researcher for their review, the orchestrator fires up a separate 'plan checking' specialist that re-analyzes the state of the underlying data and critiques the drafted analytic plan with adversarial eyes. The checker reads both Plan and Plan Tasks documents in full and works through multiple audit dimensions to ensure that the drafted plan passes internal muster before asking for any of the human expert's time. This dual-layer validation process is the crux of DAAF's 'anti-slop' strategy: any assistant producing work first conducts a thorough series of self-checks before then passing it over to a completely separate assistant for additional adversarial review and revision. Then, and only then, does DAAF escalate work products for human review.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [104, 105],
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Verified Plan.md and Plan_Tasks.md existed on disk, then read Plan.md in full to prepare the plan-checker dispatch. After the plan-checker returned PASSED_WITH_WARNINGS, the orchestrator reviewed each warning and weighed how each interacted with the original intentions and scope of the plan for any concerns to escalate to the researcher.",
        loadedFiles: [
          
          {
            name: "Plan.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md",
            kind: "file",
            note: "Strategic analytic plan specification covering the research question, methodology, the 9-dataset data design, data transformation sequence, risk register, and output specs."
          }
        ],
        producedFiles: [
          {
            name: "STATE.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md",
            kind: "file",
            note: "Updated to record the plan-checker result (passed with minor warnings, no blockers) and advance the project's phase tracking to the next stage"
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a40facd9.jsonl",
            line: 1,
            name: "Orchestrator's plan-checker dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the plan-checker specialist."
          }
        ]
      },
      {
        role: "Plan Validator",
        agentType: "plan-checker",
        task: "Read Plan.md and Plan_Tasks.md in full, then decomposed the research question into concrete data-pipeline requirements and built a coverage matrix mapping each requirement to specific tasks. Verified that all artifact paths connect cleanly between producing and consuming tasks and that the dependency chain has no circular references. Then walked through six audit dimensions (completeness, consistency, feasibility, testability, clarity, scope) and returned a structured report with per-dimension ratings, an issues list, and an explicit proceed/halt recommendation.",
        dispatch: 29,
        subagentId: "a40facd9",
        toolCalls: 3,
        loadedFiles: [
          
          {
            name: "Plan.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md",
            kind: "file",
            note: "Strategic analytic plan specification covering the research question, methodology, the 9-dataset data design, data transformation sequence, risk register, and output specs."
          },
          {
            name: "Plan_Tasks.md",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md",
            kind: "file",
            note: "Machine-readable task sequence: 33 data operations in total. Every task has explicit file paths, skill bindings, and a verifiable 'done' condition tied to a checkpoint gate, so execution cannot drift from the plan silently."
          }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a40facd9.jsonl",
            line: 11,
            name: "Plan-checker final review report",
            description: "The structured summary returned to the orchestrator. Below that, a full coverage matrix maps out what analytical requirements were checked and verified, giving the orchestrator complete transparency on what was audited and what remains unresolved before the researcher sees the plan."
          }
        ]
      }
    ]
  },

  {
    id: "checkpoint-2",
    phase: 2,
    phaseName: "Planning",
    title: "Is this the right way to approach the analysis? Will this plan as designed meet our needs?",
    type: "checkpoint",
    timeHuman: "~10 min",
    timeClaude: "~0 sec",
    description: "This is the single most consequential review point in the entire DAAF pipeline. The analytical plan has been drafted with deep insights pulled from the Discovery phase and internally reviewed. The orchestrator now pauses, presents a structured summary of the plan, and points the researcher to the full Plan file for in-depth review alongside any open design questions/issues to address. Nothing proceeds until the researcher explicitly approves. This is a crucial juncture because changes requested now are cheap: edit the plan, revalidate, then proceed. Conversely, changes requested later may require throwing away hours of downstream work. After careful inspection, the researcher can approve as-is, ask clarifying questions, request targeted methodology changes (add a control variable, change a year range), adjust scope, or push back on anything that does not match intent.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: 112
    },
    reviewItems: [
      "A high-level plan summary in the chat",
      "The full Plan.md document on disk",
      "Research question and methodology confirmed: does this match what you actually asked?",
      "Data sources confirmed with year ranges: any data quality issues you know of that DAAF has not flagged?",
      "Transformation sequence overview: does the sequence make logical sense?",
      "Research outcomes the analysis will rigorously investigate",
      "Risk register highlights (7 risks with mitigations): any risks you know of that are not listed?"
    ],
    researcherActions: [
      "Approve the plan, which authorizes all downstream code execution",
      "Request methodology changes (e.g., switch from OLS to fixed-effects regression)",
      "Adjust scope (e.g., narrow year range, add or remove data sources, add control variables)",
      "Ask clarifying questions about any plan element before deciding",
      "Push back on inappropriate or incomplete planned research outputs"
    ],
    purposeQuote: "This is your most important review point: the plan is your last chance to shape the analysis before any data is fetched, any code is written, or any computation is spent. Time spent here is the single highest-leverage activity in the entire DAAF workflow.",
    referencedFiles: [
      {
        name: "Plan.md",
        path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md",
        kind: "file",
        note: "Strategic analytic plan specification covering the research question, methodology, the 9-dataset data design, data transformation sequence, risk register, and output specs."
      },
      {
        name: "Plan_Tasks.md",
        path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md",
        kind: "file",
        note: "Machine-readable task sequence: 33 data operations in total. Every task has explicit file paths, skill bindings, and a verifiable 'done' condition tied to a checkpoint gate, so execution cannot drift from the plan silently."
      }
    ]
  },
{
    id: "step-7",
    phase: 3,
    phaseName: "Data Acquisition",
    title: "Fetching and Validating Raw Data",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~1 hour",
    description: "With the analytic plan approved, the DAAF orchestrator begins the Data Acquisition Phase by dispatching several data analysis coding specialists in parallel, each one writing a focused script to download a single dataset, run initial validation checks, and report back. After each fetch script, a completely separate code-review specialist is dispatched from an adversarial perspective to independently audit the work. This two-pass pattern (code then review) repeats throughout all coding phases. In this instance, analyses don't go quite to plan: the FSA Pell Grant recipient columns are 100% NULL for 2020 and 2021, which turns out to be a source data gap rather than a bug. The orchestrator pauses the pipeline, dispatches two search specialists in parallel to investigate alternatives, settles on IPEDS Student Financial Aid data as a workable Pell proxy, documents the substitution as a limitation, and resumes onward. DAAF's validation processes help ensure these issues are caught early, while Claude Code's inherent coding ability makes drafting principled revisions mid-flight extremely straightforward. In total: eight successful fetch scripts across two sessions, five versioned revisions, and thirteen warnings logged. Every failed script version is kept on disk with its full execution log, so the entire diagnostic trajectory is auditable end to end.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_orchestrator.jsonl",
      line: [116, 122, 126]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Read the Data Acquisition Phase workflow protocol and the task sequence from Plan_Tasks.md, then dispatched five data analysis coding specialists as a parallel batch covering the first wave of datasets (directory, admissions, graduation rates, FSA grants, enrollment by race). After every fetch script, dispatched a paired code-review specialist to independently audit the work. Nine fetch scripts plus nine independent code reviews across two sessions, with cumulative state tracked in STATE.md throughout.",
        loadedFiles: [
          
          { name: "WORKFLOW_PHASE3_ACQUISITION.md", path: "agent_reference/WORKFLOW_PHASE3_ACQUISITION.md", kind: "reference", note: "Data Acquisition Phase workflow: fetch-clean-validate protocol and parallel dispatch guidance" },
          { name: "Plan_Tasks.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md", kind: "file"}
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-29_22-31-51_137b768e_subagent_a9bf58c8.jsonl",
            line: 1,
            name: "Orchestrator's IPEDS Directory data analysis dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the IPEDS directory data analysis specialist. Note there were a LOT of these, so we'll display only one for brevity to give you the idea."
          }]
      },
      {
        role: "IPEDS Directory Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched the IPEDS institutional directory for 2020-2021, which serves as the master institution list anchoring the entire analysis. Passed validations on first attempt, confirming a complete master list of institutional characteristics, sector classifications, and geographic identifiers.",
        dispatch: 34,
        subagentId: "a9bf58c8",
        toolCalls: 17,
        loadedFiles: [
          
          { name: "education-data-query", path: ".claude/skills/education-data-query/SKILL.md", kind: "skill", note: "Skill for downloading education datasets from mirror sources" },
          { name: "fetch-patterns.md", path: ".claude/skills/education-data-query/references/fetch-patterns.md", kind: "skill", note: "Standard code patterns for fetching Portal datasets" },
          { name: "datasets-reference.md", path: ".claude/skills/education-data-query/references/datasets-reference.md", kind: "skill", note: "Catalog of dataset file paths across mirrors" },
          { name: "mirrors.yaml", path: ".claude/skills/education-data-query/references/mirrors.yaml", kind: "skill", note: "Mirror URL templates and read-strategy priority order" },
          { name: "SCRIPT_EXECUTION_REFERENCE.md", path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md", kind: "reference", note: "File-first execution protocol and script template" },
          { name: "VALIDATION_CHECKPOINTS.md", path: "agent_reference/VALIDATION_CHECKPOINTS.md", kind: "reference", note: "Stage-specific validation code templates (one per pipeline phase)" }
        ],
        producedFiles: [
          { name: "01_fetch-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py", kind: "file", note: "Fetch script for IPEDS institutional directory (2020-2021); anchors the whole analysis to its master institution list" }
        ]
      },
      {
        role: "IPEDS Admissions Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS admissions data for 2020-2021 covering applicant, admitted, and enrolled counts that will be used to derive institutional admission rates. Passed validations on first attempt.",
        dispatch: 35,
        subagentId: "ac290250",
        toolCalls: 17,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "02_fetch-admissions.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py", kind: "file", note: "Fetch script for IPEDS admissions (applicant, admit, enrollee counts) used to derive admit rates" }
        ]
      },
      {
        role: "IPEDS Graduation Rates Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched the IPEDS graduation rates dataset and immediately hit a documentation mismatch: the Plan expected a column called cohort with codes {2, 8, 12} matching the published GRTYPE scheme, but the Portal mirror actually stores it as subcohort with codes {1, 2, 99}. A perfect example of why DAAF treats skills as best-available starting points rather than ground truth: real data can drift from official documentation. v1 failed against the expected column name; v2 (03_fetch-grad-rates_a.py) switched to the actual column and codes and passed CP1. The v1 script is kept as a record of the discovery.",
        dispatch: 36,
        subagentId: "a1c3e31a",
        toolCalls: 26,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "03_fetch-grad-rates.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates.py", kind: "file", note: "First version that failed against the expected cohort column name; preserved as a record of the documentation-vs-data discovery" },
          { name: "03_fetch-grad-rates_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates_a.py", kind: "file", note: "Final version using the actual subcohort column with codes {1, 2, 99}; passed CP1" }
        ]
      },
      {
        role: "FSA Grants Data Analysis Specialist",
        agentType: "research-executor",
        task: "Tried to fetch FSA Pell grant recipient counts for 2020 and 2021. What followed is a rare but genuinely instructive DAAF failure chain. v1 crashed on a TypeError because every row had None where a number should be. v2 fixed the None handling and confirmed the grant_recipients_unitid column was 100% NULL. v3 tried a backup column (grant_recipients_opeid) and found it also 100% NULL. v4 probed year by year looking for any year where the column was populated and found none. v5 accepted that this is a Portal mirror data gap rather than a scripting error, documented the pattern formally, and returned to the orchestrator with a WARNING status. Every failed version is preserved in the project folder with its full execution log: this is what immutable audit artifact means in practice. Together the five scripts tell a diagnostic story that a human reviewer can walk through end to end.",
        dispatch: 37,
        subagentId: "afa38b32",
        toolCalls: 50,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "04_fetch-fsa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py", kind: "file", note: "v1: crashed on TypeError because the grant_recipients_unitid column was entirely None" },
          { name: "04_fetch-fsa-grants_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_a.py", kind: "file", note: "v2: fixed None handling and confirmed grant_recipients_unitid is 100% NULL" },
          { name: "04_fetch-fsa-grants_b.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_b.py", kind: "file", note: "v3: tried the grant_recipients_opeid backup column and found it also 100% NULL" },
          { name: "04_fetch-fsa-grants_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py", kind: "file", note: "v4: probed year by year for any year where the column was populated; none were" },
          { name: "04_fetch-fsa-grants_d.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_d.py", kind: "file", note: "v5 (final): accepted the Portal mirror data gap, documented the pattern formally, and returned WARNING to the orchestrator" }
        ]
      },
      {
        role: "IPEDS Enrollment Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS fall enrollment by race for 2020, the panel from which URM share will be computed downstream. Passed validations on first attempt with a perfectly balanced panel: every institution reporting across all ten race categories, with no missing cells.",
        dispatch: 38,
        subagentId: "a1626a6c",
        toolCalls: 20,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "05_fetch-enrollment-race.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/05_fetch-enrollment-race.py", kind: "file", note: "Fetch script for IPEDS fall enrollment by race (2020); the panel used to compute URM share" }
        ]
      },
      {
        role: "IPEDS Directory Code Review Specialist",
        agentType: "code-reviewer",
        task: "Audited 01_fetch-directory.py independently with a fresh context and a suspicious eye. Ran two QA diagnostic scripts and caught a subtle but consequential mistake: the open_public variable was being treated as 'open admissions' (accepts all comers), but a quick sanity check showed Harvard and Stanford both have open_public=1. The column actually means 'open to the public' (currently operating), a totally different concept. Returned a WARNING with the finding, which triggered a downstream search specialist to figure out how to recover the missing open-admissions indicator. This is exactly the type of methodological catch that embedded validation alone cannot find: it takes a second pair of eyes with the authority to stop and question.",
        dispatch: 39,
        subagentId: "acadf966",
        toolCalls: 9,
        loadedFiles: [
          
          { name: "01_fetch-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py", kind: "file", note: "The target fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_01_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr1.py", kind: "file", note: "First QA diagnostic round on 01_fetch-directory.py" },
          { name: "stage5_01_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr2.py", kind: "file", note: "Second QA diagnostic round that caught the open_public misinterpretation" }
        ]
      },
      {
        role: "IPEDS Admissions Code Review Specialist",
        agentType: "code-reviewer",
        task: "Reviewed the admissions fetch script independently and found no anomalies: all validation checks passed cleanly.",
        dispatch: 40,
        subagentId: "a380fc28",
        toolCalls: 8,
        loadedFiles: [
          
          { name: "02_fetch-admissions.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py", kind: "file", note: "The target admissions fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_02_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_02_cr1.py", kind: "file", note: "QA diagnostic for 02_fetch-admissions.py; confirmed all checks passed" }
        ]
      },
      {
        role: "IPEDS Graduation Rates Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the final version of the graduation-rates fetch (after the column name fix); ran two QA iterations confirming the subcohort coding scheme aligns with the actual data and that the completion rate is stored as a 0–1 proportion (not a 0–100 percentage).",
        dispatch: 41,
        subagentId: "a8a916a2",
        toolCalls: 9,
        loadedFiles: [
          
          { name: "03_fetch-grad-rates_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates_a.py", kind: "file", note: "Final v2 of the graduation-rates fetch under review" }
        ],
        producedFiles: [
          { name: "stage5_03_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr1.py", kind: "file", note: "First QA diagnostic round on the grad-rates fetch" },
          { name: "stage5_03_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr2.py", kind: "file", note: "Second QA diagnostic round that confirmed the 0-1 proportion encoding of completion_rate" }
        ]
      },
      {
        role: "FSA Grants Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed 04_fetch-fsa-grants_d.py (the final v5); independently confirmed the 100% NULL finding is real: the Plan explicitly noted 'Cannot compute Pell share from FSA alone' and this data quality issue will ripple downstream.",
        dispatch: 42,
        subagentId: "ad4d4b57",
        toolCalls: 12,
        loadedFiles: [
          
          { name: "04_fetch-fsa-grants_d.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_d.py", kind: "file", note: "Final v5 of the FSA fetch chain under primary review" },
          { name: "04_fetch-fsa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py", kind: "file", note: "Earlier v1 consulted for diagnostic trajectory" },
          { name: "04_fetch-fsa-grants_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py", kind: "file", note: "Intermediate v4 consulted for diagnostic trajectory" },
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Strategic plan consulted to confirm how the FSA Pell gap propagates downstream" }
        ],
        producedFiles: [
          { name: "stage5_04_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_04_cr1.py", kind: "file", note: "QA diagnostic that independently confirmed the 100% NULL finding is real" }
        ]
      },
      {
        role: "IPEDS Enrollment Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the enrollment-by-race fetch; confirmed a perfectly balanced panel with zero nulls and all population filters correctly applied.",
        dispatch: 43,
        subagentId: "a007f778",
        toolCalls: 10,
        loadedFiles: [
          
          { name: "05_fetch-enrollment-race.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/05_fetch-enrollment-race.py", kind: "file", note: "The enrollment-by-race fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_05_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_05_cr1.py", kind: "file", note: "QA diagnostic confirming the perfectly balanced panel" }
        ]
      },
      {
        role: "Pell Data Alternative Search Specialist",
        agentType: "search-agent",
        task: "Dispatched mid-flight as the orchestrator's response to the FSA Pell data gap. Loaded the education data explorer catalog and the IPEDS, FSA, and Scorecard source skills, then surveyed every plausible Pell recipient source. Returned a four-option comparison table and recommended IPEDS Student Financial Aid data, filtered to all grant types at the institution-level total, as the cleanest 2020 proxy, with the explicit caveat that this captures all grant recipients rather than Pell-specific recipients.",
        dispatch: null,
        subagentId: "ae76c810",
        toolCalls: 26,
        loadedFiles: [
          
          { name: "colleges-endpoints.md", path: ".claude/skills/education-data-explorer/references/colleges-endpoints.md", kind: "skill", note: "Portal endpoint catalog scanned for any remaining Pell-bearing dataset" },
          { name: "financial-aid.md", path: ".claude/skills/education-data-source-ipeds/references/financial-aid.md", kind: "skill", note: "IPEDS Student Financial Aid component reference, the ultimately-chosen proxy source" },
          { name: "education-data-source-fsa", path: ".claude/skills/education-data-source-fsa/SKILL.md", kind: "skill", note: "FSA source overview, consulted to confirm no alternative FSA column could substitute" },
          { name: "education-data-source-scorecard", path: ".claude/skills/education-data-source-scorecard/SKILL.md", kind: "skill", note: "Scorecard source overview, cross-checked for any Pell-recipient column (none viable)" },
          { name: "04_fetch-fsa-grants_d.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_d.py", kind: "file", note: "Final FSA fetch attempt consulted to understand the failure signature" },
          { name: "03_fetch-grad-rates_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates_a.py", kind: "file", note: "Grad-rates fetch consulted as a working Portal-fetch reference pattern" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_subagent_ae76c810.jsonl",
            line: 72,
            name: "Pell investigation Search Results report",
            description: "The Pell-alternative search-agent's full structured report. Contains the Status: PARTIAL header, the four-option comparison table (sfa_ftft, sfa_all_undergrads, Scorecard, fall back to no Pell), and the recommended IPEDS SFA proxy with the all-grant-recipients caveat."
          }
        ]
      },
      {
        role: "Open-Admissions Indicator Search Specialist",
        agentType: "search-agent",
        task: "Investigated the open_public variable after the directory QA reviewer found it means 'open to the public' (operating), not 'open admissions'; confirmed the mirror parquet omits NCES variable OPENADMP; recommended imputing open-admissions status from admissions non-reporting.",
        dispatch: null,
        subagentId: "aefe7a9e",
        toolCalls: 25,
        loadedFiles: [
          
          { name: "colleges-endpoints.md", path: ".claude/skills/education-data-explorer/references/colleges-endpoints.md", kind: "skill", note: "Portal endpoint catalog scanned for an open-admissions indicator elsewhere" },
          { name: "survey-components.md", path: ".claude/skills/education-data-source-ipeds/references/survey-components.md", kind: "skill", note: "All IPEDS survey components scanned for any column carrying admissions-openness information" },
          { name: "fetch-patterns.md", path: ".claude/skills/education-data-query/references/fetch-patterns.md", kind: "skill", note: "Fetch patterns consulted for probing raw column lists on the mirror" },
          { name: "01_fetch-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py", kind: "file", note: "Directory fetch inspected to confirm OPENADMP is absent from the mirror parquet" },
          { name: "02_fetch-admissions.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py", kind: "file", note: "Admissions fetch inspected as the candidate source for inferring open-admissions status" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_subagent_aefe7a9e.jsonl",
            line: 64,
            name: "Open Admissions Search Results report",
            description: "The Open Admissions search-agent's full structured report."
          }
        ]
      },
      {
        role: "IPEDS Student-Faculty Ratio Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS student-faculty ratio for 2020 from the HuggingFace mirror. Passed validations on first attempt.",
        dispatch: null,
        subagentId: "a505d7e2",
        toolCalls: 17,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "06_fetch-sfr.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/06_fetch-sfr.py", kind: "file", note: "Fetch script for IPEDS student-faculty ratio (2020); median SFR = 14.0" }
        ]
      },
      {
        role: "IPEDS Fall Retention Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS fall retention for 2020 and confirmed the retention rate is stored numerically, resolving a risk flagged in the risk register about potential string encoding. Passed validations on first attempt, covering all three full-time/part-time categories.",
        dispatch: null,
        subagentId: "aaff12ef",
        toolCalls: 16,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "07_fetch-retention.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/07_fetch-retention.py", kind: "file", note: "Fetch script for IPEDS fall retention (2020); confirmed retention_rate is Float64" }
        ]
      },
      {
        role: "IPEDS Finance Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS Finance for 2017, a deliberate three-year lag because instructional spending is slow-moving (per the Plan). Surfaced a subtle finding: the instructional expenditure column uses a truncated abbreviation that a naive keyword search for 'instruction' or 'expenditure' would miss entirely. This ripples into the Cleaning and Contextualizing Data step, where the search-for-the-right-column diagnostic becomes part of the script itself.",
        dispatch: null,
        subagentId: "a973f8e3",
        toolCalls: 19,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "08_fetch-finance.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/08_fetch-finance.py", kind: "file", note: "Fetch script for IPEDS finance (2017 vintage due to slow-moving instructional spending); surfaced the exp_instruc_total column-name discovery" }
        ]
      },
      {
        role: "IPEDS Student-Faculty Ratio Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the student-faculty ratio fetch; confirmed the ratio is stored as a whole number (integer truncation from the source), flagging the need for decimal conversion in the cleaning step.",
        dispatch: null,
        subagentId: "a9b15164",
        toolCalls: 10,
        loadedFiles: [
          
          { name: "06_fetch-sfr.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/06_fetch-sfr.py", kind: "file", note: "The SFR fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_06_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_06_cr1.py", kind: "file", note: "QA diagnostic that flagged the Int64 truncation downstream risk" }
        ]
      },
      {
        role: "IPEDS Fall Retention Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the retention fetch; confirmed retention rate is stored numerically (not as a text string, as the risk register feared); noted that part-time institutions frequently lack retention data, an expected IPEDS pattern.",
        dispatch: null,
        subagentId: "ad54b85c",
        toolCalls: 7,
        loadedFiles: [
          
          { name: "07_fetch-retention.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/07_fetch-retention.py", kind: "file", note: "The retention fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_07_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_07_cr1.py", kind: "file", note: "QA diagnostic confirming Float64 dtype and the expected 48.8% part-time null rate" }
        ]
      },
      {
        role: "IPEDS Finance Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the finance fetch; flagged that the script's keyword search missed the instructional expenditure column because it uses a truncated abbreviation; also noted a handful of institutions with zero full-time-equivalent enrollment, creating a downstream division-by-zero risk.",
        dispatch: null,
        subagentId: "a9f9a6a2",
        toolCalls: 11,
        loadedFiles: [
          
          { name: "08_fetch-finance.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/08_fetch-finance.py", kind: "file", note: "The finance fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_08_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_08_cr1.py", kind: "file", note: "QA diagnostic catching the exp_instruc_total column-name miss and the est_fte=0 division-by-zero risk" }
        ]
      },
      {
        role: "IPEDS SFA Pell Proxy Data Analysis Specialist",
        agentType: "research-executor",
        task: "Fetched IPEDS SFA Grants and Net Price as a Pell proxy (an unplanned addition to resolve the Pell data gap); confirmed the recommended filter combination yields institution-level grant recipient counts with complete coverage across all institutions.",
        dispatch: null,
        subagentId: "a4797e91",
        toolCalls: 17,
        loadedFiles: [
          { name: "(Same as other data pulling specialists above)", path: "", kind: "", note: "(Same as other data pulling specialists above)" }
        ],
        producedFiles: [
          { name: "09_fetch-sfa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/09_fetch-sfa-grants.py", kind: "file", note: "Unplanned Pell-proxy fetch (Task 2.4) using IPEDS SFA Grants and Net Price; 5,320 institution-level records with 100% coverage" }
        ]
      },
      {
        role: "IPEDS SFA Pell Proxy Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the SFA Pell-proxy fetch; ran two QA iterations confirming the underlying data structure (five income brackets plus one institution-wide total per school) and verifying that the totals are exact sums, not estimates.",
        dispatch: null,
        subagentId: "a1f37fb1",
        toolCalls: 9,
        loadedFiles: [
          
          { name: "09_fetch-sfa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/09_fetch-sfa-grants.py", kind: "file", note: "The SFA Pell-proxy fetch script under review" }
        ],
        producedFiles: [
          { name: "stage5_09_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr1.py", kind: "file", note: "First QA round on the SFA Pell-proxy fetch" },
          { name: "stage5_09_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr2.py", kind: "file", note: "Second QA round verifying income_level=99 as an exact total across 5,320 institutions" }
        ]
      }
    ]
  },

  {
    id: "step-8",
    phase: 3,
    phaseName: "Data Acquisition",
    title: "Cleaning and Filtering Data",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~45 min",
    description: "With the raw datasets on disk and validated, the orchestrator turns to cleaning: the work of filtering raw rows to the right population, decoding the data's missing-value codes, and computing derived measures like admission rate and share of underrepresented minority students from their component parts. DAAF handles this in parallel: eight data analysis specialists, each focused on cleaning a single dataset, each loading dataset specific domain knowledge, each running a second built-in validation check, each followed by an independent adversarial code-review specialist. One cleaning script, graduation rates, required multiple attempts because of an unforeseen data structure issue: the IPEDS graduation rate table has multiple rows per institution even within the same cohort and subcohort, and naive deduplication quietly discarded valid completion rates. It took three failed attempts and one adversarial QA pass before the final smart-dedup version preserved all 1,949 valid rates. This is the kind of quiet methodology-level error that breaks analyses downstream, and it is exactly what DAAF's dual-layer validation is designed to catch.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_orchestrator.jsonl",
      line: [206, 211]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched the data cleaning specialists plus paired code-review specialists. After each batch, surfaced a structured summary to the researcher tracking cumulative state. Recorded five cross-phase lessons to LEARNINGS.md capturing insights from the cleaning work.",
        loadedFiles: [
          
          { name: "Plan_Tasks.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md", kind: "file", note: "Task sequence consulted to dispatch the correct cleaning specialists in each wave" },
          { name: "STATE.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md", kind: "file", note: "Session state: current phase tracking and accumulated QA findings" },
          { name: "LEARNINGS.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md", kind: "file", note: "Running project-level insights file, updated as cleaning surfaces new patterns" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_subagent_a5a4ea8a.jsonl",
            line: 1,
            name: "Orchestrator's IPEDS Directory data cleaning dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the IPEDS directory data cleaning specialist. Note there were a LOT of these, so we'll display only one for brevity to give you the idea."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_orchestrator.jsonl",
            line: 224,
            name: "First cleaning batch complete summary with smart-dedup Insight",
            description: "Per-task summary table for all 5 cleaning specialists in the first batch (Directory, Admissions, Grad Rates, SFA, Enrollment Race)."
          },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_orchestrator.jsonl",
            line: 250,
            name: "Second cleaning batch complete summary",
            description: "The second summary table for the second batch, where the orchestrator confirms all three cleaning specialists in the second batch passed validations on first attempt."
          }
        ]
      },
      {
        role: "IPEDS Directory Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS directory: filtered to 4-year degree-granting institutions for 2020, replaced coded missing values, selected the core analysis columns. Passed validations on first attempt (2,893 four-year institutions, zero nulls).",
        dispatch: null,
        subagentId: "acf5d564",
        toolCalls: 18,
        loadedFiles: [
          
          { name: "education-data-context", path: ".claude/skills/education-data-context/SKILL.md", kind: "skill", note: "IPEDS-specific coded value and missingness reference" },
          { name: "ipeds-context.md", path: ".claude/skills/education-data-context/references/ipeds-context.md", kind: "skill", note: "IPEDS quirks: coded categories, missingness conventions, year alignment" },
          { name: "SCRIPT_EXECUTION_REFERENCE.md", path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md", kind: "reference", note: "File-first execution protocol" },
          { name: "VALIDATION_CHECKPOINTS.md", path: "agent_reference/VALIDATION_CHECKPOINTS.md", kind: "reference", note: "CP2 cleaning checkpoint template" },
          { name: "INLINE_AUDIT_TRAIL.md", path: "agent_reference/INLINE_AUDIT_TRAIL.md", kind: "reference", note: "IAT inline-comment standard for every transformation" }
        ],
        producedFiles: [
          { name: "01_clean-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/01_clean-directory.py", kind: "file", note: "Cleaning script that filters to 4-year degree-granting institutions and selects the 7 analysis columns" }
        ]
      },
      {
        role: "IPEDS Admissions Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS admissions: filtered to institution-level totals for year 2020 and computed the admission rate from admitted and applied counts. The cleaner landed on slightly fewer institutions than the Plan expected, which was flagged for downstream robustness checking.",
        dispatch: null,
        subagentId: "a36f2458",
        toolCalls: 15,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "02_clean-admissions.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/02_clean-admissions.py", kind: "file", note: "Cleaning script that filters to institution totals and computes admit_rate; 1,989 rows, 11 below the Plan minimum" }
        ]
      },
      {
        role: "IPEDS Graduation Rates Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned the IPEDS graduation rates dataset — the trickiest cleaning job in the phase. The first version missed a necessary population filter; the second corrected it but uncovered a deduplication trap where the default behavior silently dropped valid completion rates in favor of null ones; the third and final version implemented a smart deduplication that preserves all valid rates. Each failed version is preserved with its execution log.",
        dispatch: null,
        subagentId: "a1d9b85c",
        toolCalls: 31,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "03_clean-grad-rates.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates.py", kind: "file", note: "v1 cleaning script; missed the 4-year filter and hit 56.6% null rate" },
          { name: "03_clean-grad-rates_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_a.py", kind: "file", note: "v2 revision; added 4-year filter but subcohort=2 data was already 4-year only" },
          { name: "03_clean-grad-rates_b.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_b.py", kind: "file", note: "v3 revision; default keep='first' dedup kept null rates over valid ones" },
          { name: "03_clean-grad-rates_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_c.py", kind: "file", note: "v4 final: smart dedup sorts by completion rate desc, rescales 0-1 to 0-100" }
        ]
      },
      {
        role: "SFA Grants Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS SFA grants as Pell proxy: filtered to institution-level totals across all grant types and renamed the recipient count column for clarity. Passed validations on first attempt with complete coverage and zero nulls.",
        dispatch: null,
        subagentId: "a5248544",
        toolCalls: 21,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "04_clean-sfa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/04_clean-sfa-grants.py", kind: "file", note: "Cleaning script filtering to type_of_aid=9, income_level=99 for institution-level totals" }
        ]
      },
      {
        role: "IPEDS Enrollment Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS fall enrollment by race: computed URM share per institution as the sum of enrollment for Black, Hispanic, American Indian/Alaska Native, and Native Hawaiian/Pacific Islander students divided by total known-race enrollment. Passed validations on first attempt, with only four null URM shares — all correct edge cases (institutions with zero domestic known-race enrollment).",
        dispatch: null,
        subagentId: "a5a4ea8a",
        toolCalls: 21,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "05_clean-enrollment-race.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py", kind: "file", note: "Cleaning script computing URM share from races 2, 3, 5, 6 divided by known-race total" }
        ]
      },
      {
        role: "IPEDS Directory Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Reviewed the directory cleaning script independently: all checks passed, including verification that sector proportions and HBCU counts match known IPEDS population characteristics.",
        dispatch: null,
        subagentId: "a54c9c03",
        toolCalls: 8,
        loadedFiles: [
          
          { name: "01_clean-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/01_clean-directory.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_01_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_01_cr1.py", kind: "file", note: "Independent code-review memo: 15 checks all passed" }
        ]
      },
      {
        role: "IPEDS Admissions Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the admissions cleaning script; confirmed the admission rate computation is correct via independent recalculation; issued a warning that the row count came in slightly below the Plan's expectation.",
        dispatch: null,
        subagentId: "a2ee261a",
        toolCalls: 8,
        loadedFiles: [
          
          { name: "02_clean-admissions.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/02_clean-admissions.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_02_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_02_cr1.py", kind: "file", note: "Code-review memo: confirmed admit_rate computation, issued WARNING for 11-row shortfall" }
        ]
      },
      {
        role: "IPEDS Graduation Rates Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed 03_clean-grad-rates_c.py (final version); confirmed all 1,949 valid completion rates were preserved through the smart dedup; verified rate recalculation from completers/cohort matches within 0.05 percentage points.",
        dispatch: null,
        subagentId: "ac8aa1e5",
        toolCalls: 8,
        loadedFiles: [
          
          { name: "03_clean-grad-rates_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_c.py", kind: "file", note: "Final v4 revision of grad-rates cleaning under review" }
        ],
        producedFiles: [
          { name: "stage6_03_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_03_cr1.py", kind: "file", note: "Code-review memo: confirmed smart-dedup preserves all 1,949 valid rates" }
        ]
      },
      {
        role: "SFA Grants Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed 04_clean-sfa-grants.py; ran 2 QA iterations; confirmed the grant/student ratio is near-universal (median 0.984); documented as expected pattern, not an error; issued WARNING that this is an all-grant proxy, not Pell-specific.",
        dispatch: null,
        subagentId: "aba14d48",
        toolCalls: 11,
        loadedFiles: [
          
          { name: "04_clean-sfa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/04_clean-sfa-grants.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_04_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr1.py", kind: "file", note: "Code-review round 1 of clean-sfa-grants" },
          { name: "stage6_04_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr2.py", kind: "file", note: "Code-review round 2: confirmed grant/student ratio pattern, issued Pell-proxy WARNING" }
        ]
      },
      {
        role: "IPEDS Enrollment Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the enrollment cleaning script; verified the URM formula against raw data with zero discrepancy; confirmed the four null URM shares are correct edge cases (institutions with zero domestic known-race enrollment).",
        dispatch: null,
        subagentId: "ad0a70d7",
        toolCalls: 9,
        loadedFiles: [
          
          { name: "05_clean-enrollment-race.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_05_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py", kind: "file", note: "Code-review memo: URM formula verified, 4 nulls confirmed as edge cases" }
        ]
      },
      {
        role: "IPEDS Student-Faculty Ratio Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS student-faculty ratio: replaced coded missing values, converted from whole numbers to decimals, filtered to positive values. Passed validations on first attempt; one null removed, one extreme outlier (student-faculty ratio of 110) flagged but retained per the analytic plan.",
        dispatch: null,
        subagentId: "aaf8f32a",
        toolCalls: 13,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "06_clean-sfr.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/06_clean-sfr.py", kind: "file", note: "Cleaning script: SFR cast Int64 to Float64, null removed, SFR=110 outlier retained" }
        ]
      },
      {
        role: "IPEDS Fall Retention Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS fall retention: filtered to full-time students, discovered retention rate is stored as a 0–1 proportion and rescaled to 0–100 for consistency with graduation rates. Passed validations on first attempt with the expected pattern of missing data for part-time-only institutions documented.",
        dispatch: null,
        subagentId: "af6a9e03",
        toolCalls: 15,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "07_clean-retention.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/07_clean-retention.py", kind: "file", note: "Cleaning script: ftpt=1 filter, rescales 0-1 proportion to 0-100 scale" }
        ]
      },
      {
        role: "IPEDS Finance Data Cleaning Specialist",
        agentType: "research-executor",
        task: "Cleaned IPEDS Finance for 2017 (the Plan deliberately accepted a three-year lag because institutional finance is slow-moving). Passed validations on first attempt.",
        dispatch: null,
        subagentId: "a8f85428",
        toolCalls: 16,
        loadedFiles: [
          { name: "(Same as other data cleaning specialists above)", path: "", kind: "", note: "(Same as other data cleaning specialists above)" }
        ],
        producedFiles: [
          { name: "08_clean-finance.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/08_clean-finance.py", kind: "file", note: "Cleaning script: computes instr_expend_per_fte for 2017 with div-by-zero guard" }
        ]
      },
      {
        role: "IPEDS Student-Faculty Ratio Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Reviewed the student-faculty ratio cleaning script independently: all checks passed, including confirmation that the single institution with a null ratio was correctly removed, the numeric type conversion is correct, and the extreme outlier is documented.",
        dispatch: null,
        subagentId: "abab8cc6",
        toolCalls: 10,
        loadedFiles: [
          
          { name: "06_clean-sfr.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/06_clean-sfr.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_06_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_06_cr1.py", kind: "file", note: "Code-review memo: 15 checks passed, SFR=110 outlier documented" }
        ]
      },
      {
        role: "IPEDS Fall Retention Cleaning Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the retention cleaning script; ran two QA iterations confirming the 0-to-100 rescaling is correct and consistent with the graduation rates treatment; documented the expected null pattern for part-time-only institutions.",
        dispatch: null,
        subagentId: "a0354b50",
        toolCalls: 10,
        loadedFiles: [
          
          { name: "07_clean-retention.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/07_clean-retention.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_07_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr1.py", kind: "file", note: "Code-review round 1 of clean-retention" },
          { name: "stage6_07_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr2.py", kind: "file", note: "Code-review round 2: confirmed 0 to 100 rescaling matches grad rates treatment" }
        ]
      },
      {
        role: "IPEDS Finance Clean Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the finance cleaning script; ran two QA iterations confirming the per-student instructional spending computation is correct; flagged over a hundred potential outliers for downstream awareness but found no issues requiring a halt.",
        dispatch: null,
        subagentId: "af8588d7",
        toolCalls: 9,
        loadedFiles: [
          
          { name: "08_clean-finance.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/08_clean-finance.py", kind: "file", note: "Target cleaning script under review" }
        ],
        producedFiles: [
          { name: "stage6_08_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr1.py", kind: "file", note: "Code-review round 1 of clean-finance" },
          { name: "stage6_08_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr2.py", kind: "file", note: "Code-review round 2: confirmed per-FTE computation, flagged 134 outliers as WARNING" }
        ]
      }
    ]
  },

  {
    id: "checkpoint-3",
    phase: 3,
    phaseName: "Data Acquisition",
    title: "Are the collected datasets clean and fit-to-purpose?",
    type: "checkpoint",
    timeHuman: "~5 min",
    timeClaude: "~0 sec",
    description: "DAAF has dutifully orchestrated the fetching and cleaning of eight core datasets, running roughly thirty independent code reviews, and logging several potential data issues and interpretation implications along the way. The orchestrator now assembles a single structured data diagnostics summary and passes it to the researcher for approval: here is what arrived, here is what surprised the analysts along the way, here is what had to be substituted or worked around, and here are the judgment calls that were made. The researcher is not asked to read the raw scripts at this stage (though they can since everything is saved and auditable) -- they are asked the question any senior research colleague would ask before the statistical analysis begins: in your estimation, are the final datasets obtained close enough to expected spec to proceed? If yes, the pipeline moves into analysis. If no, the researcher can ask for different cleaning strategies, different data sources, or a formal documentation of a limitation.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_00-05-03_68a4b8f7_orchestrator.jsonl",
      line: 269
    },
    reviewItems: [
      "Does the list of datasets actually acquired match what the Plan specified?",
      "Are any sources missing entirely, or substituted with proxies you would not have chosen?",
      "For each dataset, is the missing-value rate within the range you can defend in the methods section?",
      "Did the cleaning steps remove or recode anything that should have been preserved?",
      "Are the derived variables (admission rate, URM share, grant share) computed the way you expected?",
      "Did any of the data cleaning warnings hint at a deeper issue that wasn't fully resolved in your view?",
      "Are the year selections and any deliberate lags (e.g., the 2017 Finance year in particular) acceptable for your research question?"
    ],
    researcherActions: [
      "Approve and proceed to analysis",
      "Request a different cleaning approach for one or more datasets",
      "Request re-fetching specific datasets (or a different year)",
      "Ask for a formal limitation to be documented in the final report",
      "Push back on any cleaning decision that does not feel defensible"
    ],
    purposeQuote: "I'm pausing here so you can verify that the data we fetched, cleaned, and validated is trustworthy enough to build statistical findings on. Everything from here forward, the joins, the regressions, the visualizations, rests on these datasets being sound.",
    referencedFiles: [
    ]
  },
{
    id: "step-9",
    phase: 4,
    phaseName: "Analysis",
    title: "Joining and Transforming Data",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~30 min",
    description: "With all eight cleaned datasets ready, the DAAF orchestrator then dispatches coding agents to join the separate datasets together into a unified analytic form. Each coding specialist then writes a single script that merges the next dataset onto the growing analytic file, and validates that row counts move the way the Plan predicted. As usual, a code-review specialist inspects each script before the next begins; sequential work is slower than parallel, but a broken join that silently inflates row counts would poison everything downstream, so DAAF trades speed for certainty here. After the four joins, one more specialist derives the key categorical variables the analysis will lean on: a four-way selectivity band (Highly Selective, Selective, Moderately Selective, Open/Less Selective) and Pell and URM quintiles (five equal-size groups) cut from the pooled distribution. The finished dataset: 1,946 four-year U.S. institutions, 25 variables, with every transformation traceable back to a named script and a QA memo.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_11-39-32_1886e4ed_orchestrator.jsonl",
      line: [48, 62]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched the join work one step at a time rather than in parallel, because a broken join that silently inflates row counts would poison everything downstream. After each join specialist returned, dispatched an independent code-review specialist to verify the merge before the next join could begin, trading speed for certainty.",
        loadedFiles: [
          
          { name: "Plan_Tasks.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md", kind: "file", note: "Ordered task list for the four joins in the Joining and Transforming Data step" },
          { name: "WORKFLOW_PHASE4_ANALYSIS.md", path: "agent_reference/WORKFLOW_PHASE4_ANALYSIS.md", kind: "reference", note: "Analysis Phase workflow reference covering the Joining and Transforming Data through Aggregating Quality Reviews steps" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_11-39-32_1886e4ed_subagent_a1ef7f95.jsonl",
            line: 1,
            name: "Orchestrator's first data joining dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the first data joining specialist. Note there were a LOT of these, so we'll display only one for brevity to give you the idea."
          }
        ]
      },
      {
        role: "Join Core Transform Specialist",
        agentType: "research-executor",
        task: "Joined the cleaned directory, admissions, and graduation-rates tables into the growing analysis file, validating row counts against the Plan's predictions at each merge point to catch any silent row inflation from the joins.",
        loadedFiles: [
          
          { name: "polars", path: ".claude/skills/polars/SKILL.md", kind: "skill", note: "" },
          { name: "SCRIPT_EXECUTION_REFERENCE.md", path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md", kind: "reference", note: "" },
          { name: "VALIDATION_CHECKPOINTS.md", path: "agent_reference/VALIDATION_CHECKPOINTS.md", kind: "reference", note: "CP3 transformation checkpoint template" },
          { name: "INLINE_AUDIT_TRAIL.md", path: "agent_reference/INLINE_AUDIT_TRAIL.md", kind: "reference", note: "For join logic" }
        ],
        producedFiles: [
          { name: "01_join-core.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/01_join-core.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Join Core Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed 01_join-core.py against the Plan's expected row counts and join cardinalities, verified that the left-join on unitid did not silently inflate rows, and confirmed all three source tables contributed their expected columns to the output parquet.",
        loadedFiles: [
          
          { name: "01_join-core.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/01_join-core.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage7_01_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr1.py", kind: "file", note: "" },
          { name: "stage7_01_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr2.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Join Demographics Transform Specialist",
        agentType: "research-executor",
        task: "Merged the SFA grants and enrollment-by-race tables onto the core joined dataset, validating that the row count held steady and that the new Pell-proxy and URM-share columns populated for every institution.",
        loadedFiles: [
          { name: "(Same as other data joining specialists above)", path: "", kind: "", note: "(Same as other data joining specialists above)" },
          { name: "04_clean-sfa-grants.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/04_clean-sfa-grants.py", kind: "file", note: "Upstream Pell-proxy cleaner being joined" },
          { name: "05_clean-enrollment-race.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py", kind: "file", note: "Upstream URM cleaner being joined" }
        ],
        producedFiles: [
          { name: "02_join-demographics.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/02_join-demographics.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Join Demographics Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the demographics join script; confirmed the merge preserved the expected row count, verified that Pell-proxy and URM-share columns populated as expected, and checked that the demographic tables did not introduce unexpected missing values.",
        loadedFiles: [
          
          { name: "02_join-demographics.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/02_join-demographics.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage7_02_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Join Resources Transform Specialist",
        agentType: "research-executor",
        task: "Merged the student-faculty ratio, retention, and finance tables onto the demographics output, producing the final merged dataset that feeds the selectivity band derivation and every downstream analysis.",
        loadedFiles: [
          { name: "(Same as other data joining specialists above)", path: "", kind: "", note: "(Same as other data joining specialists above)" },
          { name: "06_clean-sfr.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/06_clean-sfr.py", kind: "file", note: "Upstream SFR cleaner being joined" },
          { name: "07_clean-retention.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/07_clean-retention.py", kind: "file", note: "Upstream retention cleaner being joined" },
          { name: "08_clean-finance.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/08_clean-finance.py", kind: "file", note: "Upstream finance cleaner being joined" }
        ],
        producedFiles: [
          { name: "03_join-resources.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/03_join-resources.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Join Resources Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the resources join script; ran two QA iterations verifying the three-way merge preserved the expected row count, confirmed the finance data's deliberate three-year lag was correctly aligned, and found no issues requiring a halt.",
        loadedFiles: [
          
          { name: "03_join-resources.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/03_join-resources.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage7_03_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr1.py", kind: "file", note: "" },
          { name: "stage7_03_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr2.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Create Bands Transform Specialist",
        agentType: "research-executor",
        task: "Derived the analysis's key grouping variables from the merged dataset: a four-way selectivity band (Highly Selective through Open/Less Selective) based on admission rates, plus Pell-share and URM-share quintiles that divide institutions into five equal-sized groups for cross-tabulation. The first version failed a validation threshold; the revision adjusted the minimum group-size check and added handling for institutions with no reported admission rate.",
        loadedFiles: [
          { name: "(Same as other data joining specialists above)", path: "", kind: "", note: "(Same as other data joining specialists above)" },
          { name: "01_join-core.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/01_join-core.py", kind: "file", note: "Upstream core table where admit_rate originates" }
        ],
        producedFiles: [
          { name: "04_create-bands.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands.py", kind: "file", note: "First version; failed a validation check on minimum group size before the selectivity band thresholds were adjusted" },
          { name: "04_create-bands_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands_a.py", kind: "file", note: "Final revision: relaxed the minimum group-size check to a warning and added handling for institutions with no reported admission rate" }
        ]
      },
      {
        role: "Create Bands Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the final band-derivation script; verified the selectivity thresholds matched the Plan, confirmed the quintile cutpoints produced roughly equal-sized groups, and validated how institutions with no reported admission rate were handled (treated as open-admissions).",
        loadedFiles: [
          
          { name: "04_create-bands_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands_a.py", kind: "file", note: "Final revision of create-bands under review" }
        ],
        producedFiles: [
          { name: "stage7_04_cr1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py", kind: "file", note: "" },
          { name: "stage7_04_cr2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr2.py", kind: "file", note: "" }
        ]
      }
    ]
  },

  {
    id: "step-10",
    phase: 4,
    phaseName: "Analysis",
    title: "Running Statistical Analyses",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~30 min",
    description: "Now that the analysis dataset is assembled, the orchestrator begins dispatching the Plan's seven statistical/analytical tasks in three parallelized batches. The first batch gets the foundation in place: a descriptive snapshot of graduation rates by selectivity band, plus two cross-tabulations pairing selectivity with Pell-share and URM-share quintiles so the orchestrator can verify which institutions are inside each cell of the final dataset. The second batch layers on relationship-checking: a correlation matrix across all key variables, and an 'outperformer' flag for institutions whose actual graduation rates are higher than what a selectivity-only model would predict for them. The third batch carries the headline analyses: a hierarchical regression that builds up in four stages (selectivity alone, then adding student composition, then adding institutional resources, then a full model), and a sector-level comparison that tests whether the selectivity-to-graduation relationship looks the same at public, private nonprofit, and for-profit colleges. Seven analyses in all, each produced by its own statistical coding specialist, each paired immediately with a code-review specialist whose only job is to look for methodological problems in what was just produced. The headline numbers begin to tell a nuanced story: selectivity alone explains only about 11% of graduation-rate variation; adding student demographics bumps it to 25%; adding institutional resources, especially retention and instructional spending, pushes it past 55%.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: [52, 58, 59, 65, 85]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched the Running Statistical Analyses step in three deliberate batches: first the descriptive and cross-tab foundation, then correlation and outperformer relationship-checking, then the hierarchical regression and sector comparison. After each batch the orchestrator paused to read every QA memo and flush LEARNINGS.md before the next dispatch, so methodological problems would surface loudly before they compounded.",
        loadedFiles: [
          { name: "WORKFLOW_PHASE4_ANALYSIS.md", path: "agent_reference/WORKFLOW_PHASE4_ANALYSIS.md", kind: "reference", note: "Covering Steps 9-13" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a4c2de9d.jsonl",
            line: 1,
            name: "Descriptive analysis agent dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the first data analysis specialist."
          }
        ]
      },
      {
        role: "Descriptive by Selectivity Statistics Specialist",
        agentType: "research-executor",
        task: "Computed mean, median, and spread of graduation rates within each selectivity band, producing the 36.5-percentage-point gap that anchors the report's opening finding.",
        loadedFiles: [
          
          { name: "polars", path: ".claude/skills/polars/SKILL.md", kind: "skill", note: "For group-by aggregations" },
          { name: "SCRIPT_EXECUTION_REFERENCE.md", path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md", kind: "reference", note: "" },
          { name: "VALIDATION_CHECKPOINTS.md", path: "agent_reference/VALIDATION_CHECKPOINTS.md", kind: "reference", note: "" },
          { name: "INLINE_AUDIT_TRAIL.md", path: "agent_reference/INLINE_AUDIT_TRAIL.md", kind: "reference", note: "" },
          { name: "04_create-bands_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands_a.py", kind: "file", note: "Upstream band definition used as grouping variable" }
        ],
        producedFiles: [
          { name: "01_descriptive-by-selectivity.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Crosstab Selectivity Pell Statistics Specialist",
        agentType: "research-executor",
        task: "Cross-tabulated selectivity band against Pell-share quintile to show how graduation rates vary when both dimensions interact. The first version hit a coding library quirk; the revision resolved it cleanly.",
        loadedFiles: [
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
        ],
        producedFiles: [
          { name: "02_crosstab-selectivity-pell.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell.py", kind: "file", note: "v1 crosstab script; hit polars unpivot column collision" },
          { name: "02_crosstab-selectivity-pell_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell_a.py", kind: "file", note: "Final revision renaming the index column before unpivoting" }
        ]
      },
      {
        role: "Crosstab Selectivity URM Statistics Specialist",
        agentType: "research-executor",
        task: "Cross-tabulated selectivity band against URM-share quintile, the companion grid to the Pell crosstab above. Hit the same coding library quirk; fixed the same way on revision.",
        loadedFiles: [
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
        ],
        producedFiles: [
          { name: "03_crosstab-selectivity-urm.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm.py", kind: "file", note: "v1 URM crosstab script; same unpivot collision as Pell crosstab" },
          { name: "03_crosstab-selectivity-urm_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm_a.py", kind: "file", note: "Final revision fixing the unpivot column collision" }
        ]
      },
      {
        role: "Descriptive Batch Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed all three first-batch analysis scripts; verified the descriptive statistics matched expectations from the Plan, confirmed the crosstab grids were fully populated with no missing cells, and checked that the library-quirk fixes in the revised scripts resolved cleanly.",
        loadedFiles: [
          
          { name: "01_descriptive-by-selectivity.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py", kind: "file", note: "" },
          { name: "02_crosstab-selectivity-pell_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell_a.py", kind: "file", note: "" },
          { name: "03_crosstab-selectivity-urm_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm_a.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage8_01_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_01_cra1.py", kind: "file", note: "" },
          { name: "stage8_01_cra2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_01_cra2.py", kind: "file", note: "" },
          { name: "stage8_02_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_02_cra1.py", kind: "file", note: "" },
          { name: "stage8_07_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra1.py", kind: "file", note: "" },
          { name: "stage8_07_cra2.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra2.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Correlation Matrix Statistics Specialist",
        agentType: "research-executor",
        task: "Built a correlation matrix showing how each of the seven key variables (graduation rate, admission rate, Pell share, URM share, retention rate, instructional spending, and endowment per student) relate to each other. Hit the same data-reshaping library quirk as the crosstabs; the revision resolved it the same way.",
        loadedFiles: [
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
        ],
        producedFiles: [
          { name: "04_correlation-matrix.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix.py", kind: "file", note: "v1 correlation matrix script; hit the unpivot collision" },
          { name: "04_correlation-matrix_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix_a.py", kind: "file", note: "Final revision renaming variable column before unpivoting" }
        ]
      },
      {
        role: "Outperformers Statistics Specialist",
        agentType: "research-executor",
        task: "Identified institutions that graduate students at substantially higher rates than their selectivity level alone would predict, by fitting a simple model and flagging schools whose actual rates exceeded expectations by more than one standard deviation. Nearly 250 institutions made the 'outperformer' list, and these are the schools labeled by name in the residual-scatter visualization.",
        loadedFiles: [
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
          { name: "statsmodels", path: ".claude/skills/statsmodels/SKILL.md", kind: "skill", note: "For OLS and residuals" },
          { name: "linear-models.md", path: ".claude/skills/statsmodels/references/linear-models.md", kind: "skill", note: "" },
          { name: "statistical-modeling.md", path: ".claude/skills/data-scientist/references/statistical-modeling.md", kind: "skill", note: "For OLS and residual diagnostics" }
        ],
        producedFiles: [
          { name: "05_outperformers.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/05_outperformers.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Relationship Checking Batch Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the correlation matrix and outperformer scripts; verified the correlation values were internally consistent, confirmed the outperformer threshold (one standard deviation above predicted) matched the Plan, and cross-checked the outperformer identification against the regression output to make sure no institution was incorrectly flagged.",
        loadedFiles: [
          
          { name: "04_correlation-matrix.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix.py", kind: "file", note: "" },
          { name: "05_outperformers.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/05_outperformers.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage8_04_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_04_cra1.py", kind: "file", note: "" },
          { name: "stage8_05_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_05_cra1.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Regression Models Statistics Specialist",
        agentType: "research-executor",
        task: "Ran the headline regression analysis, building up in four stages to isolate what actually drives graduation rates: first selectivity alone, then adding student demographics, then institutional resources like retention and instructional spending, then the full model. Used a statistical approach that accounts for unequal variance across institutions. Over 80% of institutions had complete data for all variables, well above the Plan's conservative worst-case estimate.",
        loadedFiles: [
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
          { name: "statsmodels", path: ".claude/skills/statsmodels/SKILL.md", kind: "skill", note: "For hierarchical OLS and HC1 SEs" },
          { name: "statistical-modeling.md", path: ".claude/skills/data-scientist/references/statistical-modeling.md", kind: "skill", note: "For hierarchical regression" },
          { name: "linear-models.md", path: ".claude/skills/statsmodels/references/linear-models.md", kind: "skill", note: "" },
          { name: "diagnostics.md", path: ".claude/skills/statsmodels/references/diagnostics.md", kind: "skill", note: "" }
        ],
        producedFiles: [
          { name: "06_regression-models.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Sector Comparison Statistics Specialist",
        agentType: "research-executor",
        task: "Ran the selectivity-graduation relationship analysis separately for public, private nonprofit, and for-profit colleges, exposing a striking pattern that became one of the report's headline findings: at public and private nonprofit schools, more selective institutions graduate students at higher rates, but at for-profit schools the relationship runs in the opposite direction.",
        loadedFiles: [
          
          { name: "(Same as other data analysis specialists above)", path: "", kind: "", note: "(Same as other data analysis specialists above)" },
          { name: "descriptive-analysis.md", path: ".claude/skills/data-scientist/references/descriptive-analysis.md", kind: "skill", note: "For subgroup comparison" }
        ],
        producedFiles: [
          { name: "07_sector-comparison.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Headline Regression Batch Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the regression and sector-comparison scripts; verified that the explanatory power increased as expected when each new predictor block was added, confirmed the variance-adjustment technique was correctly applied, and checked that the analysis handled the much smaller for-profit subsample appropriately given its limited size.",
        loadedFiles: [
          
          { name: "06_regression-models.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py", kind: "file", note: "" },
          { name: "07_sector-comparison.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage8_06_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_06_cra1.py", kind: "file", note: "" },
          { name: "stage8_03_cra1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_03_cra1.py", kind: "file", note: "" }
        ]
      }
    ]
  },

  {
    id: "step-11",
    phase: 4,
    phaseName: "Analysis",
    title: "Creating Visualizations",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~20 min",
    description: "With the statistical results in hand, the orchestrator brings in five data visualization specialists at once, one per headline figure, and dispatches them to work in parallel. Each one loads the plotnine skill (Python's grammar-of-graphics library, modeled on R's ggplot2), reads up on the embedded reference files on data visualization best practices, picks a colorblind-safe palette, sets sensible image formatting parameters for publication-readiness, and writes a single visualization script that turns a specific analytic output into a useful and concise figure. This is also the step where the AI agent's self revision loop is perhaps most obviously helpful: DAAF handles all the idiosyncrasies and difficulties of iterating to get a plot 'just right' without issue. For example, the scatter specialist's first script passed QA muster immediately. But the boxplot specialist needed three versions to resolve a visualization library quirk. The heatmap-by-Pell specialist needed four versions to tackle legend labeling and point label mismatches. The correlation-heatmap specialist hit a column-name issue on its first data reshaping attempt. The sector-comparison specialist struggled to unshrink the proportions of the facet panels. Because Claude can actually visually inspect each output, these processes catch not just coding issues, but also valuable aesthetic and readability issues as well.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: [164, 179, 186]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched five visualization specialists in parallel, each handed a single figure with a colorblind-safe palette and publication-quality export settings. Paused after all five returned to dispatch a single batch quality review over the whole set, then dispatched a follow-up round for the residual scatter.",
        loadedFiles: [
          { name: "WORKFLOW_PHASE4_ANALYSIS.md", path: "agent_reference/WORKFLOW_PHASE4_ANALYSIS.md", kind: "reference", note: "For visualization dispatch" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a4edbb6e.jsonl",
            line: 1,
            name: "Data visualization specialist dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the first data visualization specialist."
          }
        ]
      },
      {
        role: "Scatter Grad vs Admit Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a scatter plot showing how graduation rates relate to admission rates across all institutions with reported admission data. Passed validation on the first try — the simplest of the six figures and a useful anchor for what a clean visualization pass looks like.",
        loadedFiles: [
          
          { name: "plotnine", path: ".claude/skills/plotnine/SKILL.md", kind: "skill", note: "" },
          { name: "SCRIPT_EXECUTION_REFERENCE.md", path: "agent_reference/SCRIPT_EXECUTION_REFERENCE.md", kind: "reference", note: "" },
          { name: "visualization-design.md", path: ".claude/skills/data-scientist/references/visualization-design.md", kind: "skill", note: "" },
          { name: "visualization-execution.md", path: ".claude/skills/data-scientist/references/visualization-execution.md", kind: "skill", note: "" },
          { name: "geoms.md", path: ".claude/skills/plotnine/references/geoms.md", kind: "skill", note: "For point and smooth" },
          { name: "scales-coords.md", path: ".claude/skills/plotnine/references/scales-coords.md", kind: "skill", note: "" },
          { name: "facets-themes.md", path: ".claude/skills/plotnine/references/facets-themes.md", kind: "skill", note: "" },
          { name: "gotchas.md", path: ".claude/skills/plotnine/references/gotchas.md", kind: "skill", note: "" },
          { name: "INLINE_AUDIT_TRAIL.md", path: "agent_reference/INLINE_AUDIT_TRAIL.md", kind: "reference", note: "" }
        ],
        producedFiles: [
          { name: "08_viz-scatter-grad-admit.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/08_viz-scatter-grad-admit.py", kind: "file", note: "Scatter plot script for Figure 2, 1,625 institutions" },
          { name: "2026-03-29_grad_rate_vs_admission_rate.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png", kind: "file", note: "" }
        ]
      },
      {
        role: "Boxplot Selectivity Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a boxplot of graduation rates within each selectivity band. Needed three versions to get right: the first failed on a function-call syntax issue in the plotting library, the second failed on unsupported color names, and the third landed cleanly. A good example of DAAF handling the fiddly iteration a researcher would otherwise have to chase manually.",
        loadedFiles: [
          { name: "(Same as other data visualization specialists above)", path: "", kind: "", note: "(Same as other data visualization specialists above)" },
        ],
        producedFiles: [
          { name: "09_viz-boxplot-selectivity.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity.py", kind: "file", note: "v1 boxplot script; stat_summary expected string name, not callable" },
          { name: "09_viz-boxplot-selectivity_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_a.py", kind: "file", note: "v2 boxplot; R-style color names not resolved by mizani" },
          { name: "09_viz-boxplot-selectivity_b.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_b.py", kind: "file", note: "Final v3 boxplot with corrected stat_summary and palette" },
          { name: "2026-03-29_boxplot_grad_rate_by_selectivity.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png", kind: "file", note: "Figure 1: graduation rates by selectivity band boxplot" }
        ]
      },
      {
        role: "Heatmap Selectivity Pell Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a heatmap of graduation rates by selectivity band and Pell quintile. Needed four versions, each failing a different validation check on issues like column-name mismatches, deprecated plotting arguments, and outdated library syntax, before landing cleanly. The most iterated figure in the whole pipeline, and the one that best illustrates what the write-validate-revise loop does for a researcher who would otherwise have to chase each of these plotting-library gotchas alone.",
        toolCalls: 38,
        loadedFiles: [
          { name: "(Same as other data visualization specialists above)", path: "", kind: "", note: "(Same as other data visualization specialists above)" },
        ],
        producedFiles: [
          { name: "10_viz-heatmap-selectivity-pell.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py", kind: "file", note: "v1 heatmap script; column-name n vs N mismatch broke pivot" },
          { name: "10_viz-heatmap-selectivity-pell_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_a.py", kind: "file", note: "v2 heatmap; deprecated guide_colorbar(barwidth=) argument" },
          { name: "10_viz-heatmap-selectivity-pell_b.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_b.py", kind: "file", note: "v3 heatmap; guide=False argument not recognized in modern plotnine" },
          { name: "10_viz-heatmap-selectivity-pell_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_c.py", kind: "file", note: "Final v4 heatmap that landed cleanly" },
          { name: "2026-03-29_heatmap_selectivity_pell.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png", kind: "file", note: "Figure 3: heatmap of graduation rates by selectivity band and Pell quintile" },
          { kind: "log-line", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl", line: 197, name: "Heatmap 4-version failure table", description: "The full four-row version-history table inside the orchestrator's visualization summary: v1 column-name n vs N, v2 deprecated guide_colorbar(barwidth=), v3 guide=False not recognized, v4 PASSED. The single most show-don't-tell artifact in the Analysis Phase." }
        ]
      },
      {
        role: "Correlation Heatmap Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a correlation heatmap showing relationships between all key variables. Hit the same data-reshaping library quirk that tripped the earlier crosstab scripts; the revision resolved it the same way and landed cleanly.",
        loadedFiles: [
          { name: "(Same as other data visualization specialists above)", path: "", kind: "", note: "(Same as other data visualization specialists above)" },
        ],
        producedFiles: [
          { name: "11_viz-correlation-heatmap.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap.py", kind: "file", note: "v1 correlation heatmap script; polars unpivot collision" },
          { name: "11_viz-correlation-heatmap_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap_a.py", kind: "file", note: "Final revision renaming index column before unpivoting" },
          { name: "2026-03-29_correlation_heatmap.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_correlation_heatmap.png", kind: "file", note: "Figure 6: 7x7 correlation matrix heatmap" },
          { kind: "log-line", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl", line: 197, name: "Correlation heatmap unpivot gotcha", description: "The visualization summary's note on this figure: 'Polars DuplicateError: unpivot column name collision with existing variable column.' Same root cause as the earlier crosstabs; fixed the same way on the _a revision." }
        ]
      },
      {
        role: "Sector Comparison Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a three-panel comparison of the selectivity-graduation relationship across public, private nonprofit, and for-profit sectors. The first revision fixed a plotting-library argument issue; later revisions came during the final-review pass in the Synthesis Phase after the verifier flagged that the panels were too narrow and the axis labels overlapped.",
        loadedFiles: [
          { name: "(Same as other data visualization specialists above)", path: "", kind: "", note: "(Same as other data visualization specialists above)" },
        ],
        producedFiles: [
          { name: "12_viz-sector-comparison.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison.py", kind: "file", note: "v1 sector-comparison script; plotnine guide=False argument issue" },
          { name: "12_viz-sector-comparison_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison_a.py", kind: "file", note: "Initial-dispatch revision removing guide=False" },
          { name: "2026-03-29_sector_comparison.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_sector_comparison.png", kind: "file", note: "Figure 5: three-panel sector comparison" }
        ]
      },
      {
        role: "Visualization Batch Code Review Specialist",
        agentType: "code-reviewer",
        task: "Reviewed all five figures as a single quality batch, loading every script and every rendered image. The only review in the pipeline that inspected the actual visual output alongside source code, because visualization errors often live in pixels rather than logic.",
        loadedFiles: [
          
          { name: "08_viz-scatter-grad-admit.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/08_viz-scatter-grad-admit.py", kind: "file", note: "" },
          { name: "09_viz-boxplot-selectivity_b.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_b.py", kind: "file", note: "" },
          { name: "10_viz-heatmap-selectivity-pell_c.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_c.py", kind: "file", note: "" },
          { name: "11_viz-correlation-heatmap_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap_a.py", kind: "file", note: "" },
          { name: "12_viz-sector-comparison_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison_a.py", kind: "file", note: "" },
          { name: "grad_rate_vs_admission_rate.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png", kind: "file", note: "" },
          { name: "boxplot_grad_rate_by_selectivity.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png", kind: "file", note: "" },
          { name: "heatmap_selectivity_pell.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png", kind: "file", note: "" },
          { name: "correlation_heatmap.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_correlation_heatmap.png", kind: "file", note: "" },
          { name: "sector_comparison.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_sector_comparison.png", kind: "file", note: "" }
        ],
        producedFiles: [
          { name: "stage8_08_crb1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_08_crb1.py", kind: "file", note: "" }
        ]
      },
      {
        role: "Residual Scatter Visualization Specialist",
        agentType: "research-executor",
        task: "Produced a follow-up actual-vs-predicted scatter with the top eight outperformer institutions labeled by name. Passed validation on the first try; later revisions happened during the final-review pass in the Synthesis Phase, documented in that step rather than here.",
        loadedFiles: [
          { name: "(Same as other data visualization specialists above)", path: "", kind: "", note: "(Same as other data visualization specialists above)" },
        ],
        producedFiles: [
          { name: "13_viz-residual-scatter.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter.py", kind: "file", note: "Residual scatter script labeling the top 8 outperformer institutions" },
          { name: "2026-03-29_actual_vs_predicted.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_actual_vs_predicted.png", kind: "file", note: "Figure 4: actual vs. predicted graduation-rate scatter" }
        ]
      },
      {
        role: "Residual Scatter Code Review Specialist",
        agentType: "code-reviewer",
        task: "Independently reviewed the residual scatter script and its rendered image; verified the top-eight outperformer labels matched the list from the earlier outperformer analysis, confirmed the predicted-vs-actual trend line was correctly computed, and checked that the diagonal reference line (where predicted equals actual) was present for visual comparison.",
        loadedFiles: [
          
          { name: "13_viz-residual-scatter.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter.py", kind: "file", note: "" },
          { name: "actual_vs_predicted.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_actual_vs_predicted.png", kind: "file", note: "" },
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Plan reference for residual scatter specifications" }
        ],
        producedFiles: [
          { name: "stage8_13_crb1.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_13_crb1.py", kind: "file", note: "" }
        ]
      }
    ]
  },

  {
    id: "step-12",
    phase: 4,
    phaseName: "Analysis",
    title: "Compiling the Interactive Notebook",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~10 min",
    description: "Now the orchestrator brings in a specialist whose entire job is to create a single, unified Python notebook that allows the researcher to review the complete pipeline of finalized analytic scripts and analytic output in one interactive place. The notebook-assembly specialist reads all 30 final script files (one per task, plus their appended execution logs) and copies them verbatim into a single reproducibility notebook, preserving every line of code and every captured output block. No regeneration, no re-analysis, no smoothing over the rough edges. This hard constraint is what makes the notebook trustworthy: what you see in the notebook is exactly what actually ran during the analysis, with nothing silently rewritten by an LLM after the fact. This product facilitates easier human review (e.g., to allow them to interactively inspect intermediary datasets) and also powers DAAF's separate Reproducibility Verification mode, in which DAAF procedurally re-runs, and validates the reproducibility of, any previously completed DAAF analysis with a full reproducibility report.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: 226
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched the notebook-assembler with an unusually narrow prompt: act as a compiler, not an analyst. The dispatch prompt explicitly forbids regeneration, re-analysis, or smoothing; the only new code allowed is a handful of one-line data-loading cells for interactive browsing.",
        loadedFiles: [
          { name: "WORKFLOW_PHASE4_ANALYSIS.md", path: "agent_reference/WORKFLOW_PHASE4_ANALYSIS.md", kind: "reference", note: "For notebook assembly" },
        ],
        producedFiles: [
          { kind: "log-line", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a25e1198.jsonl", line: 1, name: "Notebook compiler dispatch prompt", description: "The prompt the DAAF Orchestrator wrote to launch the notebook-assembler" }
        ]
      },
      {
        role: "Notebook Assembly Specialist",
        agentType: "notebook-assembler",
        task: "Read every final script and its appended execution log from all four pipeline stages, copied each into the interactive notebook verbatim (no summarization, no regeneration), wrapped execution logs in collapsible sections for cleaner browsing, added lightweight data-loading cells so the researcher can interactively inspect any intermediate dataset, and verified the finished notebook runs cleanly before returning.",
        toolCalls: 26,
        loadedFiles: [
          
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Plan reference to orient on the set of final scripts" },
          { name: "01_fetch-directory.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py", kind: "file", note: "Representative example script loaded as part of the verbatim-copy pass" },
          { name: "notebook.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py", kind: "file", note: "Target marimo notebook being assembled" },
          { name: "marimo", path: ".claude/skills/marimo/SKILL.md", kind: "skill", note: "" }
        ],
        producedFiles: [
          { name: "_build_notebook.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/_build_notebook.py", kind: "file", note: "Build script that stitches scripts and logs into the notebook" },
          { name: "notebook.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py", kind: "file", note: "Final interactive notebook compiling every analysis script and its execution log into a single browseable walkthrough" },
          { kind: "log-line", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a25e1198.jsonl", line: 71, name: "Notebook-assembler's final report", description: "The specialist's structured final message: 30 scripts compiled, 144 cells (15,514 lines), all 34 data and figure references resolve cleanly, marimo run verification passed." }
        ]
      }
    ]
  },

  {
    id: "checkpoint-4",
    phase: 4,
    phaseName: "Analysis",
    title: "Do the high-level results make sense and meet expectations?",
    type: "checkpoint",
    timeHuman: "~5 min",
    timeClaude: "~0 sec",
    description: "The orchestrator stops dispatching work and puts everything the Analysis Phase produced back on the researcher's desk at once: the assembled analysis dataset, all headline statistical results, all figures with their documented caveats, the aggregated quality-review summary, and the compiled interactive notebook. It lays out the findings in plain prose: the large graduation-rate gap across selectivity bands, the fact that selectivity alone explains only about 11% of graduation-rate variation while adding institutional resources pushes it past 55%, and the striking finding that the selectivity effect shrinks by more than half once you account for what institutions actually invest in their students. Then it asks one question directly: 'Do these results make sense substantively? Are they complete and to-spec?' The final in-depth analytic report runs on whatever the researcher says here. This is the chance to flag surprising results for a second look, to request an extra visualization, to push back on an interpretation, or to simply approve and proceed.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: 229
    },
    reviewItems: [
      "Does the final analysis dataset (1,946 four-year U.S. institutions × 25 variables) match the scope you set in the Plan? Any institution types you expected to see and don't?",
      "Do the seven statistical results answer the research questions you wrote down? Effect sizes included, not just p-values.",
      "Look at all six figures with their caveats: scatter, boxplot, heatmap, correlation heatmap, sector comparison, residual scatter. Do any of them mislead, hide variation, or over-annotate?",
      "Review the aggregated quality findings from the code reviews. Were any concerns discussed informally during the work that didn't make it into the formal review memos?",
      "Key known limitations grouped by theme: the Pell-share proxy (all-grant count rather than Pell-only), the small Highly Selective tier (only 71 institutions), the three-year finance data lag, and three visualization annotation caveats. Do any of these change how you'd interpret the findings?",
      "The hypothesis assessment found that selectivity alone is a weaker predictor than expected, student demographics do meaningfully mediate the relationship, and institutional resources matter at least as much as selectivity. Does this match your substantive expectations?",
      "The interactive notebook compiles every analysis script and its output into a single browseable walkthrough. Can you open it and browse to a random analysis to confirm it renders cleanly?"
    ],
    researcherActions: [
      "Approve and proceed to report writing",
      "Request additional analyses or visualizations before the report begins",
      "Request a re-run of any analysis with different specifications",
      "Flag a specific figure or table for deeper investigation before the report is written",
      "Push back on any interpretation that does not match your substantive expectations"
    ],
    purposeQuote: "Do the results make sense substantively? Are there additional analyses or visualizations you'd like to see? Any results that seem surprising and worth investigating further?",
    referencedFiles: [
    ]
  },
{
    id: "step-14",
    phase: 5,
    phaseName: "Synthesis",
    title: "Writing the Report",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~20 min",
    description: "With the fourth checkpoint approved, the DAAF orchestrator begins the Synthesis Phase by collecting all 62 session logs for by this project into a single project folder so that every file needed for a complete audit is self-contained and in one place, then verifies that all key files for the report exist on disk. It then dispatches a report-writing specialist assistant whose job is synthesis and science communication: take the plan, the notebook, the statistical outputs, the six figures, and the running session notes, and turn all of it into an summary analytical report the human expert can actually review altogether. The specialist is deliberately grounded in every artifact the pipeline produced so that every claim in the report can be traced back from something that was really computed, not reconstructed from the LLM's fuzzy memory. The result is an in-depth analytic report with an executive summary, key findings tied to specific figures, an honest limitations section, the citations tracked throughout execution, and a transparent AI use disclosure documenting exactly how automated assistance was used in producing the analysis. This report serves as a grounded building block for all future possible deliverables from here: interactive dashboard visualizations, academic paper drafting, policymaker memos, robustness checks and extensions, and so on.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: [234, 237, 242]
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Loaded the Synthesis Phase workflow reference, collected all 62 session logs touched by this project into the project folder so every file needed for audit was in one place, verified that all 6 figures existed on disk, then dispatched the report-writing specialist with the full context bundle: the plan, notebook, statistical outputs, figures, session state, and accumulated lessons learned.",
        loadedFiles: [
          
          { name: "WORKFLOW_PHASE5_SYNTHESIS.md", path: "agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md", kind: "reference", note: "Synthesis Phase workflow reference for report, verification, delivery" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_ae89a77f.jsonl",
            line: 1,
            name: "Report writer dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the report writing specialist."
          }
        ]
      },
      {
        role: "Report Writing Specialist",
        agentType: "report-writer",
        task: "Read the report template, AI disclosure reference, citation conventions, the frozen research plan, the compiled notebook, and the session state, then synthesized the full pipeline's artifacts into a stakeholder-facing analytical report. Every numerical claim in the report was traced back to a specific source script so that reviewers can verify any finding end-to-end. The report includes an executive summary written for a non-technical audience, a findings section organized around each research outcome and hypothesis the plan defined, an honest limitations section, and a transparent AI use disclosure documenting exactly how automated assistance contributed to the analysis.",
        loadedFiles: [
          
          { name: "REPORT_TEMPLATE.md", path: "agent_reference/REPORT_TEMPLATE.md", kind: "reference", note: "" },
          { name: "AI_DISCLOSURE_REFERENCE.md", path: "agent_reference/AI_DISCLOSURE_REFERENCE.md", kind: "reference", note: "" },
          { name: "CITATION_REFERENCE.md", path: "agent_reference/CITATION_REFERENCE.md", kind: "reference", note: "" },
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Grounds every numerical claim in the report" },
          { name: "STATE.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md", kind: "file", note: "Session state including hypothesis assessment and QA aggregation" },
          { name: "LEARNINGS.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md", kind: "file", note: "" },
          { name: "notebook.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py", kind: "file", note: "Source for numerical claims" },
          { name: "heatmap_selectivity_pell.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png", kind: "file", note: "Representative figure loaded with 5 others for report body" },
          { name: "plain-language.md", path: ".claude/skills/science-communication/references/plain-language.md", kind: "skill", note: "Used for executive summary" }
        ],
        producedFiles: [
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "Final stakeholder report covering every research outcome and hypothesis defined in the plan, with findings tied to specific figures and a transparent AI use disclosure" }
        ]
      }
    ]
  },

  {
    id: "step-15",
    phase: 5,
    phaseName: "Synthesis",
    title: "Independent Final Verification",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~20 min",
    description: "The DAAF orchestrator now dispatches a verification specialist assistant whose entire job is to be extremely skeptical of the validity of the drafted analytical report: to approach it assuming something has been transcribed incorrectly, something has been overstated, or something has been quietly lost in translation between script and prose. DAAF's design assumes that any translation from computed numbers to written prose can introduce drift unless independently checked, and the report is where that risk is perhaps most consequential. The verifier runs six in-depth checks to assess the possibility for a variety of LLM-induced errors (existence, substantiveness, wiring, coherence, a research question stress test, and the 'Telephone Game' trace that follows each key finding backward from the report claim all the way to the raw script output). In this analysis, the Telephone Game caught what it was designed to catch: the report had transcribed several plausible-looking numbers that did not exactly match what the scripts actually computed, most consequentially a regression coefficient error that changed the entire attenuation narrative of the analysis. The orchestrator immediately cross-referenced the verifier's findings against the regression script's execution log, confirmed the errors were real, and dispatched a second report-writer pass to fix the flagged values. This is what DAAF's dual-layer validation looks like at the final stage of the pipeline, and why the framework builds independent verification into the workflow rather than trusting the first draft.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: 245
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Dispatched the data-verifier for the Independent Final Verification step, received the ISSUES_FOUND return with BLOCKER-severity transcription errors, read the verifier's findings in-context and cross-referenced them against the regression script's execution log to confirm the errors were real, then dispatched a second report-writer for a targeted correction pass (a correction pass, not a rewrite).",
        loadedFiles: [
          
          { name: "06_regression-models.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py", kind: "file", note: "Source regression script cross-referenced against report claims" },
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "First-draft report loaded for verifier dispatch and correction-pass review" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a10136df.jsonl",
            line: 1,
            name: "Report verifier dispatch prompt",
            description: "The prompt the DAAF Orchestrator actually wrote to launch the report verifier specialist."
          }
        ]
      },
      {
        role: "Verification Specialist",
        agentType: "data-verifier",
        task: "Read the draft report, the frozen plan, the session state, the compiled notebook, and four analysis scripts — all with adversarial intent. Worked through a series of verification checks: confirming every referenced file and figure actually exists, testing whether findings genuinely answer the original research question, verifying that data flows correctly between scripts, and most critically, running what the framework calls the 'Telephone Game' — tracing key statistics end-to-end from the report's prose back through the notebook to the raw script execution logs to see if anything was lost in translation. The Telephone Game caught what it was designed to catch: multiple transcription errors including a regression coefficient that had been plausibly hallucinated rather than copied from the actual output. Returned the findings to the orchestrator as blockers requiring correction before the report could be delivered.",
        loadedFiles: [
          
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Plan reference for research-question stress test" },
          { name: "STATE.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md", kind: "file", note: "Session state reference for coherence checks" },
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "Draft report under adversarial review" },
          { name: "notebook.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py", kind: "file", note: "Telephone Game trace source" },
          { name: "06_regression-models.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py", kind: "file", note: "Regression script consulted for coefficient trace" },
          { name: "01_descriptive-by-selectivity.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py", kind: "file", note: "Descriptive statistics script consulted for gap-number trace" },
          { name: "heatmap_selectivity_pell.png", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png", kind: "file", note: "Representative figure loaded with 5 others for existence verification" }
        ],
        producedFiles: [
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_subagent_a10136df.jsonl",
            line: 118,
            name: "Report verifier final report",
            description: "The summary report the verifier passed back to the orchestrator with its findings."
          }
        ]
      },
      {
        role: "Report Writing Correction Pass Specialist",
        agentType: "report-writer",
        task: "Loaded the first-draft report alongside the four analysis scripts the verifier had flagged, then systematically corrected each numerical error the verification pass had surfaced — including the hallucinated regression coefficient that had changed the attenuation narrative of the analysis. Before writing any corrected value, verified it against the script's actual execution log to ensure the report now faithfully reflects what was really computed.",
        loadedFiles: [
          
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "Draft report loaded for targeted correction" },
          { name: "01_descriptive-by-selectivity.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py", kind: "file", note: "Descriptive script re-checked for corrected gap values" },
          { name: "06_regression-models.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py", kind: "file", note: "Regression script re-checked for coefficient and R^2 corrections" },
          { name: "04_correlation-matrix_a.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix_a.py", kind: "file", note: "Correlation matrix script re-checked for pairwise r values" },
          { name: "07_sector-comparison.py", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py", kind: "file", note: "Sector comparison script re-checked for per-sector statistics" }
        ],
        producedFiles: [
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "Revised report with all flagged transcription errors corrected and verified against source script outputs" }
        ]
      }
    ]
  },

  {
    id: "step-16",
    phase: 5,
    phaseName: "Synthesis",
    title: "Consolidation and Delivery",
    type: "step",
    timeHuman: "~0 sec",
    timeClaude: "~5 min",
    description: "With the verified report in hand, the DAAF orchestrator consolidates everything for final delivery. It reads the updated lessons-learned log and adds insights surfaced from the most recent steps, then generates a concrete DAAF-improvement plan that maps each learning to a specific DAAF file with a proposed change to prevent similar issues in the future, identifying eight improvements that this single analysis surfaced. This iterative self-improvement engine in DAAF allows it to continuously adapt to and learn from any work you do with it, the same way human researchers do: by doing real data analysis, running into issues, figuring out what went wrong, and updating protocols and documentation so those issues can be avoided next time. After wrapping up some archival logistics, the DAAF orchestrator then passes the full package to the researcher: a plain-language summary of what was found, the exact file paths for the Plan, Notebook, Report, Data, Figures, and Learnings, a data citation ready to paste, and an offer to incorporate the framework improvements in a follow-up session. Everything from the audit trail is now in the researcher's hands, self-contained and reviewable, for human evaluation and judgment of where to take the analysis from here.",
    orchestratorLogLine: {
      path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
      line: 273
    },
    agentFlow: [
      {
        role: "DAAF Orchestrator",
        agentType: "orchestrator",
        task: "Wrapped up the analysis by consolidating everything the pipeline had learned along the way — from the data challenges discovered during coding through the transcription errors the verification pass caught — into the project's lessons-learned log. Then went a step further: mapped each lesson to a specific file in the DAAF framework itself with a proposed change, so that future analyses benefit from what this one surfaced. Finalized the project tracking state, and delivered the full package to the researcher: a plain-language summary of what was found, the complete file inventory (Plan, Notebook, Report, Data, Figures, and Learnings), a ready-to-paste data citation, and an offer to incorporate the framework improvements in a follow-up session.",
        loadedFiles: [
          
          { name: "LEARNINGS.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md", kind: "file", note: "Consolidated with insights from Running Statistical Analyses onward" },
          { name: "STATE.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md", kind: "file", note: "Session state finalized at end of pipeline" },
          { name: "Report.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md", kind: "file", note: "Final verified report used for delivery summary" },
          { name: "Plan.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md", kind: "file", note: "Referenced in delivery inventory" }
        ],
        producedFiles: [
          { name: "LEARNINGS.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md", kind: "file", note: "Late-pipeline insights appended, plus a System Update Action Plan mapping each lesson to a specific DAAF file with proposed changes for future analyses" },
          { name: "STATE.md", path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/STATE.md", kind: "file", note: "Final verification step marked complete, project finalized" },
          {
            kind: "log-line",
            path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/logs/2026-03-30_17-06-00_4297744d_orchestrator.jsonl",
            line: 273,
            name: "Final delivery message to researcher",
            description: "The orchestrator's closing delivery: plain-language summary of what was found, 6 key findings, 5-item limitations summary, data citation ready to paste, the complete file inventory (Plan, Notebook, Report, Data, Figures, Learnings), and an offer to incorporate the 8 framework improvements in a follow-up Framework Development session. This is the final entry in the pipeline's narrative arc."
          }
        ]
      }
    ]
  }]
;

    const PHASE_METADATA = [
        { id: 1, name: "Discovery",        subtitle: "What data can we use to answer this question?", sectionId: "phase-1" },
        { id: 2, name: "Planning",         subtitle: "How exactly will we analyze these datasets?",         sectionId: "phase-2" },
        { id: 3, name: "Data Acquisition", subtitle: "Time to obtain, process, and transform the data",         sectionId: "phase-3" },
        { id: 4, name: "Analysis",         subtitle: "Answering the actual research questions with the data",      sectionId: "phase-4" },
        { id: 5, name: "Synthesis",        subtitle: "Packaging everything for delivery and review",    sectionId: "phase-5" },
    ];

    // §§ MODULE_STATE ==================================================
    // activeStepIndex: null = not yet initialized, -1 = intro, 0..n = step
    // lockScrollObserver: prevents scroll/intersection races during programmatic navigation
    // panelRenderToken: monotonic counter used to guard async right-panel
    //   renders from stale callbacks. Every updateRightPanel() call
    //   increments it; any async continuation (e.g. a log-line fetch)
    //   captures the token before starting and only applies its result
    //   when the captured token still matches the current token. This
    //   prevents late-arriving fetches from clobbering newer state.
    // ================================================================
    let activeStepIndex = null;
    let stepElements = [];
    let progressDots = [];
    let lockScrollObserver = false;
    let panelRenderToken = 0;
    let mobileSheetOpen = false;

    // §§ DOM_REFERENCES (cached on init) ============================== */
    let leftPanel, panelContent, panelTypeLabel, panelTitle, referencePanel, nextStepsSection;
    let mobilePill, mobileBackdrop, mobilePillLabel;
    const mobileQuery = window.matchMedia('(max-width: 900px)');
    // Dynamic scroll offset: nav height (mobile progress bar removed)
    function scrollHeaderOffset() {
        return NAV_HEIGHT;
    }

    // §§ PHASE_HELPERS =================================================
    // Phase/checkpoint color resolution lives in CSS via [data-phase]
    // attribute inheritance. These helpers just return the attribute value.
    // ================================================================
    function phaseAttr(step) { return step.type === 'checkpoint' ? 'cp' : String(step.phase); }

    // §§ NORMALIZE_FILE ================================================
    // The phase data uses two shapes for loadedFiles/producedFiles:
    //   Phases 1–2: array of { name, path, kind, note } objects
    //   Phases 3–5: array of plain string paths (sometimes with
    //     parenthetical clarifications like "STATE.md (many updates)")
    // normalizeFile accepts either and returns a uniform object.
    //
    // Naming improvements (e version): for skills referenced as
    // ".claude/skills/{name}/SKILL.md", the visible name is the parent
    // directory ({name}), not the literal "SKILL.md". For agent files,
    // the trailing ".md" is stripped from the visible name.
    // ================================================================
    function inferKind(p) {
        if (p.startsWith('.claude/skills/')) return 'skill';
        if (p.startsWith('.claude/agents/'))  return 'agent';
        if (p.startsWith('agent_reference/')) return 'reference';
        if (/\.(py|sh)$/i.test(p))            return 'script';
        return 'file';
    }
    function deriveName(path, kind) {
        let name = path.split('/').pop();
        if (kind === 'skill' && /SKILL\.md$/i.test(path)) {
            const parts = path.split('/');
            name = parts[parts.length - 2] || name;
        } else if (kind === 'agent' && /\.md$/i.test(name)) {
            name = name.replace(/\.md$/i, '');
        }
        return name;
    }
    function normalizeFile(f) {
        if (typeof f === 'string') {
            const raw = f.trim();
            const cleanPath = raw.replace(/\s*\([^)]*\)\s*$/, '').trim();
            const kind = inferKind(cleanPath);
            return { name: deriveName(cleanPath, kind), path: cleanPath, kind: kind, note: '' };
        }
        // Object — fill missing fields
        const out = Object.assign({}, f);
        // Log-line entries reference a specific JSONL message inside a
        // local session log. Required fields: path (relative URL to the
        // .jsonl file) and line (1-indexed). Optional: name, description.
        if (out.kind === 'log-line') {
            out.path = out.path || '';
            out.line = out.line || 1;
            if (!out.name) {
                const baseName = (out.path.split('/').pop() || 'log').replace(/\.jsonl?$/i, '');
                out.name = baseName + ' · L' + out.line;
            }
            if (out.note === undefined) out.note = '';
            return out;
        }
        if (!out.path) return out;
        if (!out.kind) out.kind = inferKind(out.path);
        if (!out.name) out.name = deriveName(out.path, out.kind);
        if (out.note === undefined) out.note = '';
        return out;
    }

    function fileIcon(kind) {
        switch (kind) {
            case 'skill':     return '\uD83D\uDCDA'; // 📚
            case 'agent':     return '\uD83D\uDC64'; // 👤 (silhouette — f version)
            case 'reference': return '\uD83D\uDCD1'; // 📑
            case 'script':    return '\uD83D\uDCDC'; // 📜
            case 'log-line':  return '\uD83D\uDCAC'; // 💬
            default:          return '\uD83D\uDCC4'; // 📄
        }
    }

    function escapeAttr(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // §§ FILE_HELPERS_E ================================================
    // Image-path detection (for short-circuiting binary fetches into
    // direct <img> renders) and per-file plain-language descriptions
    // for the Read More "Files Referenced" / "Files Produced" rows.
    // ================================================================
    function isImagePath(p) {
        return /\.(png|jpe?g|gif|svg|webp|bmp|ico)$/i.test(p || '');
    }

    // Returns a one-sentence description for a normalized file object.
    // (f version) Resolution order:
    //   1. Explicit caller override (nf.description)
    //   2. Full-path lookup in FILE_DESCRIPTIONS (primary — every file
    //      referenced in PIPELINE_STEPS has an entry)
    //   3. Legacy keyed lookups (skill parent-dir, agent basename,
    //      bare basename) — kept as belt-and-suspenders fallback for
    //      any file added later that isn't yet in the path-keyed map
    //   4. Script-stage inference from path
    //   5. Kind-based generic fallback
    function describeFile(nf) {
        if (!nf || !nf.path) return '';
        if (nf.description) return nf.description;
        // Log-line entries get a synthesized default description if the
        // caller hasn't supplied one — they're a special case because the
        // path-keyed lookup would be ambiguous (one file, many lines).
        if (nf.kind === 'log-line') {
            return 'A specific message from this session log (line ' + nf.line + ').';
        }
        // (1) Primary: full-path lookup.
        if (FILE_DESCRIPTIONS[nf.path]) return FILE_DESCRIPTIONS[nf.path];
        // (2) Legacy keyed fallbacks (only reached for paths missing
        // from the path-keyed map — should be rare post-f).
        if (nf.kind === 'skill') {
            const parts = nf.path.split('/');
            const skillKey = parts[parts.length - 2];
            if (FILE_DESCRIPTIONS[skillKey]) return FILE_DESCRIPTIONS[skillKey];
        }
        if (nf.kind === 'agent') {
            const key = (nf.name || '').replace(/\.md$/i, '');
            if (FILE_DESCRIPTIONS[key]) return FILE_DESCRIPTIONS[key];
        }
        const basename = nf.path.split('/').pop();
        if (FILE_DESCRIPTIONS[basename]) return FILE_DESCRIPTIONS[basename];
        // (3) Script-stage inference.
        if (nf.kind === 'script') {
            const lower = nf.path.toLowerCase();
            const stageMap = {
                fetch:     'A Python script that fetches raw data from a federal data source.',
                clean:     'A Python script that cleans and standardizes a fetched dataset.',
                join:      'A Python script that joins datasets together on common keys.',
                transform: 'A Python script that derives analytical variables from cleaned data.',
                analyze:   'A Python script that runs a statistical analysis on the analytical dataset.',
                analysis:  'A Python script that runs a statistical analysis on the analytical dataset.',
                visualize: 'A Python script that produces a visualization from the analytical dataset.',
                viz:       'A Python script that produces a visualization from the analytical dataset.',
                qa:        'A Python script that performs an automated quality check on the data or outputs.',
            };
            for (const stage in stageMap) {
                if (lower.indexOf('/scripts/' + stage + '/') !== -1) return stageMap[stage];
            }
            return 'A Python analysis script in this project.';
        }
        // (4) Kind-based generic fallback.
        if (nf.kind === 'reference') return 'A workflow reference document used by the DAAF orchestrator at this stage.';
        if (nf.note) return nf.note;
        return 'A project file used or produced at this step.';
    }

    // §§ DOCUMENT_FETCHING (GitHub raw, memoized) ======================
    // Pass { silent: true } to skip the panel-wide loading-state takeover
    // (used by buildReportFragment, which renders its own inline spinner
    // inside the original-query callout it just constructed).
    const documentCache = new Map();

    async function fetchDocument(path, opts) {
        if (documentCache.has(path)) return documentCache.get(path);
        const silent = opts && opts.silent;
        if (!silent) showLoadingState();
        try {
            const response = await fetch(GITHUB_RAW_BASE + path);
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const text = await response.text();
            documentCache.set(path, text);
            return text;
        } catch (err) {
            return null;
        }
    }

    function showLoadingState() {
        panelContent.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading document...</div></div>';
    }

    // §§ MARKDOWN_RENDERING (regex-based, sufficient for our content) --
    function renderMarkdown(md) {
        let html = md;
        html = html.replace(/&(?!amp;|lt;|gt;|quot;|#)/g, '&amp;');
        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) => {
            const escaped = code.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            if (lang === 'py' || lang === 'python') return '<pre>' + highlightPython(escaped) + '</pre>';
            return '<pre>' + escaped + '</pre>';
        });
        // Tables
        html = html.replace(/^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm, (m, header, sep, body) => {
            const ths = header.split('|').filter(c => c.trim()).map(c => '<th>' + c.trim() + '</th>').join('');
            const rows = body.trim().split('\n').map(row => {
                const tds = row.split('|').filter(c => c.trim()).map(c => '<td>' + c.trim() + '</td>').join('');
                return '<tr>' + tds + '</tr>';
            }).join('');
            return '<table><thead><tr>' + ths + '</tr></thead><tbody>' + rows + '</tbody></table>';
        });
        html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
        html = html.replace(/^---$/gm, '<hr>');
        // Join consecutive plain-text lines into single paragraphs.
        // Standard Markdown: blank lines separate paragraphs; consecutive
        // non-blank, non-block-element lines form one paragraph. Without
        // this, hard-wrapped .md files render each source line as its own <p>.
        const mdLines = html.split('\n');
        const mdJoined = [];
        const isPlain = (l) => l && l.trim() !== '' && !/^<[hupoltb\/]/.test(l.trimStart());
        for (let i = 0; i < mdLines.length; i++) {
            if (isPlain(mdLines[i]) && mdJoined.length > 0 && isPlain(mdJoined[mdJoined.length - 1])) {
                mdJoined[mdJoined.length - 1] += ' ' + mdLines[i];
            } else {
                mdJoined.push(mdLines[i]);
            }
        }
        html = mdJoined.join('\n');
        html = html.replace(/^(?!<[hupoltb]|<\/|<li|<hr|<blockquote)(.+)$/gm, '<p>$1</p>');
        // Images — rewrite relative figure paths to GitHub raw.
        // The regex tolerates trailing content after the closing )
        // because the line-joining step above can merge a standalone
        // image line with an adjacent italic caption (e.g.,
        // *Figure 1: description*) into a single <p>.
        html = html.replace(/<p>!\[([^\]]*)\]\(([^)]+)\)(.*?)<\/p>/g, (m, alt, src, trailing) => {
            if (src.startsWith('output/figures/')) {
                const filename = src.split('/').pop();
                const key = Object.keys(FIGURES).find(k => filename.includes(k));
                if (key) src = FIGURES[key];
            }
            let result = '<img src="' + src + '" alt="' + alt + '" loading="lazy"><div class="figure-caption">' + alt + '</div>';
            if (trailing && trailing.trim()) {
                result += '<p class="figure-note">' + trailing.trim() + '</p>';
            }
            return result;
        });
        return html;
    }

    // §§ PYTHON_HIGHLIGHTING (token-safe) ------------------------------
    // Extract comments/strings first as placeholders, highlight keywords/numbers
    // on the safe text, then restore the tokens to avoid regex collisions
    // (e.g. `class` keyword matching `class=` inside a stashed HTML span).
    function highlightPython(code) {
        const tokens = [];
        let idx = 0;
        function stash(cls, text) {
            const placeholder = '\x00T' + (idx++) + '\x00';
            tokens.push({ placeholder, html: '<span class="syntax-' + cls + '">' + text + '</span>' });
            return placeholder;
        }
        let safe = code;
        safe = safe.replace(/("""[\s\S]*?"""|'''[\s\S]*?''')/g, (m) => stash('string', m));
        safe = safe.replace(/(#.*)$/gm, (m) => stash('comment', m));
        safe = safe.replace(/(f?r?b?)(["'])(?:(?!\2|\\).|\\.)*\2/g, (m) => stash('string', m));
        safe = safe.replace(/(@\w+)/g, (m) => stash('decorator', m));
        const keywords = 'def|class|import|from|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|with|as|try|except|finally|raise|pass|break|continue|lambda|yield|assert|del|global|nonlocal|async|await';
        safe = safe.replace(new RegExp('\\b(' + keywords + ')\\b', 'g'), (m) => stash('keyword', m));
        safe = safe.replace(/\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/gi, (m) => stash('number', m));
        tokens.forEach(t => { safe = safe.split(t.placeholder).join(t.html); });
        return safe;
    }

    // §§ RENDER_IMAGE_IN_PANEL =========================================
    // Short-circuits binary image files (PNG/JPG/GIF/SVG/WebP) into a
    // direct <img> render pointing at the GitHub raw URL. Used by the
    // file-ref click handler before any text-based fetch happens —
    // fetching binary as response.text() decodes garbage and hangs the
    // browser, so this path bypasses fetchDocument() entirely.
    // ================================================================
    function renderImageInPanel(path, title) {
        const blobUrl   = GITHUB_BLOB_BASE + path;
        const rawUrl    = GITHUB_RAW_BASE + path;
        const niceTitle = title || path.split('/').pop();
        panelTypeLabel.innerHTML = 'Figure / Image';
        panelTitle.textContent   = niceTitle;
        panelContent.innerHTML =
            '<div class="document-viewer">' +
              '<div class="document-header">' +
                '<span class="document-path">' + path + '</span>' +
                '<a class="document-github-link" href="' + blobUrl + '" target="_blank" rel="noopener">View on GitHub \u2197</a>' +
              '</div>' +
              '<div class="document-content">' +
                '<img class="fetched-image" src="' + rawUrl + '" alt="' + escapeAttr(niceTitle) + '" loading="lazy">' +
                '<div class="fetched-image-caption">' + escapeAttr(niceTitle) + '</div>' +
              '</div>' +
            '</div>';
        referencePanel.scrollTop = 0;
    }

    // §§ FETCH_LOG_LINE ================================================
    // Loads a JSONL session log file from GitHub raw and returns the
    // parsed JSON object at the given 1-indexed line. The whole file
    // is cached in `logFileCache` after the first fetch so repeated
    // line lookups against the same file are free.
    //
    // Paths stored in PIPELINE_STEPS use the full repo-relative form:
    //   'research/2026-03-29_.../logs/FILENAME.jsonl'
    // which resolves to GITHUB_RAW_BASE + path at fetch time.
    //
    // To reference a log line from PIPELINE_STEPS, add an entry of the
    // shape { kind: 'log-line', path: LOG_DIR + 'foo.jsonl',
    //        line: 42, name: 'Final summary', description: '...' }
    // to a step's loadedFiles or producedFiles array.
    // ================================================================
    const logFileCache = new Map();
    async function fetchLogLine(path, line) {
        if (!path) return null;
        if (!logFileCache.has(path)) {
            try {
                const response = await fetch(GITHUB_RAW_BASE + path);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const text = await response.text();
                // Split on newlines but drop trailing empty line.
                const lines = text.split('\n').filter(l => l.length > 0);
                logFileCache.set(path, lines);
            } catch (err) {
                logFileCache.set(path, null);
                return null;
            }
        }
        const lines = logFileCache.get(path);
        if (!lines) return null;
        const idx = parseInt(line, 10) - 1;
        if (idx < 0 || idx >= lines.length) return null;
        try {
            return JSON.parse(lines[idx]);
        } catch (err) {
            return null;
        }
    }

    // Multi-line convenience wrapper. Accepts either a single line
    // number or an array of line numbers and returns a Promise that
    // resolves to an array of parsed objects in the same order as the
    // request (with nulls for lines that failed to load or parse). The
    // underlying `fetchLogLine()` caches the whole file on its first
    // call, so the N per-line parses after that are effectively free.
    //
    // Used by the `updateRightPanel()` step branch when a step's
    // `orchestratorLogLine.line` is an array — e.g. step-3 showing the
    // orchestrator's thinking + speaking arc around the parallel
    // dispatch of 3 source researchers.
    async function fetchLogLines(path, lineOrLines) {
        const lineArr = Array.isArray(lineOrLines) ? lineOrLines : [lineOrLines];
        return Promise.all(lineArr.map(n => fetchLogLine(path, n)));
    }

    // §§ BUILD_LOG_MESSAGE_BODY_HTML ===================================
    // Takes a parsed JSONL record from a Claude Code session log and
    // returns the `.log-message` card as an HTML string. Reusable by
    // both the file-ref click flow (renderLogMessageInPanel) and the
    // step-default-view flow (updateRightPanel's log-line branch),
    // which each set their own panel-header type label + title before
    // inserting this body.
    //
    // Handles the message-shape variants Claude Code emits:
    //   - obj.message.content as a string  → renderMarkdown directly
    //   - obj.message.content as an array  → walk content blocks
    //       • {type:'text', text}                → markdown
    //       • {type:'tool_use', name, input}     → indigo tool-call card
    //       • {type:'tool_result', content}      → tool-result card
    // Anything else falls through to a JSON dump so the user still
    // sees something useful for unfamiliar message shapes.
    //
    // (08b) The header was simplified: the old "ASSISTANT" role badge
    // + filename/line/timestamp metadata span were both removed in
    // favor of a single static "DAAF Assistant Message Logs" label,
    // matching how the step-default transcript view reads.
    //
    // Optional `hideHeader` boolean suppresses the card header
    // entirely (no `.log-message-header` element at all). The
    // multi-line step-default flow uses this for cards 2..N of a
    // `.log-message-group`, so only the first card in the stack
    // shows the label and subsequent cards read as a continuous
    // thread.
    // ================================================================
    function buildLogMessageBodyHtml(obj, hideHeader) {
        const role = obj && obj.message && obj.message.role;
        const isUser = role === 'user';
        const content = obj && obj.message && obj.message.content;
        let bodyHtml = '';
        if (typeof content === 'string') {
            bodyHtml = renderMarkdown(content);
        } else if (Array.isArray(content)) {
            bodyHtml = content.map(block => {
                if (!block || typeof block !== 'object') return '';
                if (block.type === 'text') {
                    return renderMarkdown(block.text || '');
                }
                // Thinking blocks are the AI's internal reasoning traces
                // that Claude Code emits before visible output. Rendering
                // them gives the explainer an authentic peek at the
                // orchestrator's reasoning, not just its final prose.
                // (08b) Added because step-2 references a thinking-only
                // line in the session log — without this handler it
                // would render as "(empty message body)".
                if (block.type === 'thinking') {
                    return (
                        '<div class="log-message-thinking">' +
                            '<div class="log-message-thinking-label">\u2605 Internal Reasoning</div>' +
                            '<div class="log-message-thinking-body">' + renderMarkdown(block.thinking || block.text || '') + '</div>' +
                        '</div>'
                    );
                }
                if (block.type === 'tool_use') {
                    let inputStr = '';
                    try { inputStr = JSON.stringify(block.input, null, 2); }
                    catch (e) { inputStr = String(block.input); }
                    return (
                        '<div class="log-message-toolcall">' +
                            '<div class="log-message-toolcall-name">\u2192 ' + escapeAttr(block.name || 'tool') + '</div>' +
                            '<pre>' + escapeAttr(inputStr) + '</pre>' +
                        '</div>'
                    );
                }
                if (block.type === 'tool_result') {
                    let resultText;
                    if (typeof block.content === 'string') {
                        resultText = block.content;
                    } else if (Array.isArray(block.content)) {
                        resultText = block.content.map(c => (c && c.text) ? c.text : JSON.stringify(c)).join('\n');
                    } else {
                        try { resultText = JSON.stringify(block.content, null, 2); }
                        catch (e) { resultText = String(block.content); }
                    }
                    // Cap to a reasonable size — log lines can have huge
                    // tool results that would dominate the panel.
                    const capped = resultText.length > 2400
                        ? resultText.slice(0, 2400) + '\n\n[\u2026 truncated, ' + (resultText.length - 2400) + ' more chars]'
                        : resultText;
                    return (
                        '<div class="log-message-toolcall">' +
                            '<div class="log-message-toolcall-name">\u2190 Tool Result</div>' +
                            '<pre>' + escapeAttr(capped) + '</pre>' +
                        '</div>'
                    );
                }
                return '';
            }).join('');
        } else if (obj) {
            // Unfamiliar shape — show a pretty-printed JSON dump so the
            // user still sees the underlying record.
            let dump;
            try { dump = JSON.stringify(obj, null, 2); }
            catch (e) { dump = String(obj); }
            bodyHtml = '<pre>' + escapeAttr(dump) + '</pre>';
        }

        if (!bodyHtml) bodyHtml = '<p><em>(empty message body)</em></p>';

        const roleLabel = isUser ? 'Researcher Prompt' : 'DAAF Assistant Message Logs';
        const headerHtml = hideHeader
            ? ''
            : ('<div class="log-message-header' + (isUser ? ' log-message-header-user' : '') + '">' +
                   '<span class="log-message-role">' + roleLabel + '</span>' +
               '</div>');
        return (
            '<div class="log-message' + (isUser ? ' log-message-user' : '') + '">' +
                headerHtml +
                '<div class="log-message-body">' + bodyHtml + '</div>' +
            '</div>'
        );
    }

    // §§ LOG_TRANSCRIPT_LINK =============================================
    // Returns a .document-header bar linking to the human-readable .md
    // transcript on GitHub, matching the layout used by the document
    // viewer (path on the left, "View on GitHub" link on the right).
    // The .md file is the parallel sibling of the .jsonl — same name,
    // different extension. Placed ABOVE the log-message card(s).
    // ================================================================
    function logTranscriptLinkHtml(jsonlPath) {
        if (!jsonlPath) return '';
        const mdPath = jsonlPath.replace(/\.jsonl$/, '.md');
        const blobUrl = GITHUB_BLOB_BASE + mdPath;
        const filename = mdPath.split('/').pop();
        return (
            '<div class="document-header log-transcript-header">' +
                '<span class="document-path">' + filename + '</span>' +
                '<a class="document-github-link" href="' + blobUrl + '" target="_blank" rel="noopener">View full transcript on GitHub \u2197</a>' +
            '</div>'
        );
    }

    // §§ RENDER_LOG_MESSAGE_IN_PANEL ===================================
    // Thin wrapper that sets the panel-wide header and drops in the
    // log-message body. Used by the file-ref click flow — when the
    // user clicks a log-line file ref, this path fires and the panel
    // title shows the filename + line number.
    //
    // (08b) The step-default view uses a separate inline code path in
    // updateRightPanel() that shares the same buildLogMessageBodyHtml
    // helper but sets different panel-header text (step title + the
    // "Session Transcript" type label).
    // ================================================================
    function renderLogMessageInPanel(obj, path, line, label) {
        const filename = path.split('/').pop() || path;
        panelTypeLabel.textContent = 'Log Message';
        panelTitle.textContent = label || (filename + ' · L' + line);
        panelContent.innerHTML = logTranscriptLinkHtml(path) + buildLogMessageBodyHtml(obj);
        referencePanel.scrollTop = 0;
    }

    // §§ DOCUMENT_RENDER (render fetched file to panel) ----------------
    function renderDocumentInPanel(path, content, title) {
        const ext = path.split('.').pop().toLowerCase();
        let cleanContent = content;
        // Strip YAML frontmatter from markdown files so agent/skill metadata doesn't render.
        if (ext === 'md' && content.startsWith('---')) {
            const endIdx = content.indexOf('---', 3);
            if (endIdx !== -1) cleanContent = content.slice(endIdx + 3).trim();
        }

        let rendered;
        if (ext === 'py' || ext === 'sh') {
            const escaped = cleanContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            rendered = '<pre class="code-block">' + highlightPython(escaped) + '</pre>';
        } else if (ext === 'md') {
            rendered = renderMarkdown(cleanContent);
        } else {
            const escaped = cleanContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            rendered = '<pre class="code-block">' + escaped + '</pre>';
        }

        const blobUrl = GITHUB_BLOB_BASE + path;
        panelTypeLabel.innerHTML = ext === 'py' ? 'Python Script' : ext === 'md' ? 'Markdown Document' : 'File';
        panelTitle.textContent = title || path.split('/').pop();
        panelContent.innerHTML =
            '<div class="document-viewer">' +
              '<div class="document-header">' +
                '<span class="document-path">' + path + '</span>' +
                '<a class="document-github-link" href="' + blobUrl + '" target="_blank" rel="noopener">View on GitHub \u2197</a>' +
              '</div>' +
              '<div class="document-content">' + rendered + '</div>' +
            '</div>';
        referencePanel.scrollTop = 0;
    }

    // §§ REPORT_HYDRATION ==============================================
    // (e version) Builds a thin shell containing the original-prompt
    // callout and an empty report-body slot, then asynchronously fetches
    // the full Report.md from GitHub and renders it as markdown into the
    // slot. This replaces the d version's hand-curated inline report
    // template — the right panel now shows the actual final report file,
    // mirroring how every other document in the explainer is loaded.
    //
    // The fetch uses { silent: true } so fetchDocument's panel-wide
    // loading-state takeover does not blow away the original-query
    // callout we just rendered above the slot.
    // ================================================================
    function buildReportFragment() {
        const wrap = document.createElement('div');
        wrap.className = 'report-content';
        wrap.innerHTML =
            '<div class="document-header">' +
                '<span class="document-path">' + REPORT_PATH + '</span>' +
                '<a class="document-github-link" href="' + REPORT_BLOB_URL + '" target="_blank" rel="noopener">View on GitHub \u2197</a>' +
            '</div>' +
            '<div class="original-query">' +
                '<div class="query-label">The Original Prompt</div>' +
                '<blockquote class="original-prompt"></blockquote>' +
            '</div>' +
            '<div class="report-body">' +
                '<div class="loading-state">' +
                    '<div class="loading-spinner"></div>' +
                    '<div class="loading-text">Loading the full report from GitHub\u2026</div>' +
                '</div>' +
            '</div>';
        wrap.querySelector('.original-prompt').innerHTML = USER_PROMPT.replace(/\n\n/g, '<br><br>');

        fetchDocument(REPORT_PATH, { silent: true }).then(content => {
            const slot = wrap.querySelector('.report-body');
            if (!slot) return; // user navigated away mid-fetch
            if (!content) {
                slot.innerHTML =
                    '<div class="fetch-error">Failed to load the full report.' +
                    '<br><br><a href="' + REPORT_BLOB_URL + '" target="_blank" rel="noopener">View on GitHub \u2197</a></div>';
                return;
            }
            // Strip YAML frontmatter if present
            let cleanContent = content;
            if (content.startsWith('---')) {
                const endIdx = content.indexOf('---', 3);
                if (endIdx !== -1) cleanContent = content.slice(endIdx + 3).trim();
            }
            slot.innerHTML = renderMarkdown(cleanContent);
        });

        return wrap;
    }

    // §§ BUILD_PROGRESS_RAIL ========================================== */
    function buildProgressRail() {
        const rail = document.getElementById('progress-rail');
        let currentPhase = 0;
        let stepNum = 0;
        let cpNum = 0;

        PIPELINE_STEPS.forEach((step, index) => {
            if (step.phase !== currentPhase) {
                currentPhase = step.phase;
                const label = document.createElement('div');
                label.className = 'progress-rail-phase-label';
                label.dataset.phase = String(currentPhase);
                label.textContent = 'P' + currentPhase;
                rail.appendChild(label);
            }

            const dot = document.createElement('div');
            dot.className = 'progress-dot' + (step.type === 'checkpoint' ? ' checkpoint-dot' : '');
            dot.dataset.phase = phaseAttr(step);
            dot.dataset.index = index;

            if (step.type === 'checkpoint') cpNum++; else stepNum++;
            const tooltipText = step.type === 'checkpoint'
                ? ('CP' + cpNum + ': ' + step.title)
                : ('Step ' + stepNum + ': ' + step.title);
            const tooltip = document.createElement('div');
            tooltip.className = 'progress-dot-tooltip';
            tooltip.textContent = tooltipText;

            dot.addEventListener('click', () => {
                const idx = parseInt(dot.dataset.index, 10);
                if (idx >= 0 && idx < stepElements.length) {
                    scrollToStepTop(stepElements[idx]);
                    setTimeout(() => setActiveStep(idx, true), 500);
                }
            });

            // Wrap dot + tooltip as siblings so the tooltip is NOT inside the
            // rotated coordinate system of checkpoint diamonds.
            const wrap = document.createElement('div');
            wrap.className = 'progress-dot-wrap';
            wrap.appendChild(dot);
            wrap.appendChild(tooltip);

            progressDots.push(dot);
            rail.appendChild(wrap);
        });
    }

    function updateProgressRail(index) {
        progressDots.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
            dot.classList.toggle('past', i < index);
        });
    }

    // §§ BUILD_AGENT_FLOW ==============================================
    // Renders the ordered agent-flow cards for the step-detail Read More.
    //
    // (e version) Layout changes:
    //   • The agent-type pill and the dispatch/id/calls metadata strip
    //     have been removed from the card header. The role h4 is now
    //     the first visible element.
    //   • The two file lists are no longer side-by-side bag-of-pills.
    //     Each is a labelled section ("Primary Files Referenced" /
    //     "Primary Files Produced") containing two-column rows: file ref on the left,
    //     plain-language description on the right (via describeFile()).
    //   • The agent's own spec (from AGENT_SPECS) is hoisted to the top
    //     of Files Referenced and marked .is-spec, replacing the old
    //     clickable header pill. If the data already lists the spec, we
    //     hoist the existing entry; otherwise we synthesize one and
    //     attach the agent's role description as its row description.
    // ================================================================
    function buildAgentFlow(step) {
        if (!step.agentFlow || step.agentFlow.length === 0) {
            return '<div class="agent-flow-empty">The DAAF orchestrator handled this step directly — no specialist assistants dispatched.</div>';
        }
        const phaseAttrVal = phaseAttr(step);
        const items = step.agentFlow.map(entry => {
            // Resolve the displayed agent description from the canonical
            // AGENT_DESCRIPTIONS map first; fall back to the per-dispatch
            // entry.agentDescription only if the agentType is unknown.
            // This keeps the "what kind of specialist is this?" blurb
            // identical everywhere the same agent type shows up, while
            // the per-dispatch `task` field still carries step-specific
            // detail.
            const resolvedDesc = AGENT_DESCRIPTIONS[entry.agentType] || entry.agentDescription;

            // —— Primary Files Referenced ————————————————————————
            // Hoist or synthesize the agent's own spec into position 0.
            let loaded = (entry.loadedFiles || []).map(normalizeFile);
            const synthSpec = AGENT_SPECS[entry.agentType];
            if (synthSpec) {
                const existingIdx = loaded.findIndex(f => f.path === synthSpec);
                let specEntry;
                if (existingIdx >= 0) {
                    specEntry = loaded.splice(existingIdx, 1)[0];
                } else {
                    const isSkillSpec = synthSpec.indexOf('/skills/') !== -1;
                    const kind = isSkillSpec ? 'skill' : 'agent';
                    specEntry = {
                        name: deriveName(synthSpec, kind),
                        path: synthSpec,
                        kind: kind,
                        note: ''
                    };
                }
                specEntry.isSpec = true;
                // Let describeFile() resolve normally so the spec row gets
                // the file-oriented description from FILE_DESCRIPTIONS,
                // not the agent-type blurb (which is already shown in the
                // card header as agent-flow-agent-desc).
                specEntry.description = describeFile(specEntry);
                loaded = [specEntry].concat(loaded);
            }

            // —— Primary Files Produced ——————————————————————————
            const produced = (entry.producedFiles || []).map(normalizeFile);

            const renderRow = (f) => {
                const desc      = describeFile(f);
                // Log-line rows carry the line number in a separate
                // data attribute and route through fetchLogLine() in
                // the click handler. Everything else fetches via the
                // normal GitHub-raw path.
                if (f.kind === 'log-line') {
                    const titleAttr = f.path + ':L' + f.line;
                    return (
                        '<div class="agent-flow-file-row is-log-line">' +
                            '<span class="file-ref clickable log-line-ref" ' +
                                'data-file-path="' + escapeAttr(f.path) + '" ' +
                                'data-log-line="' + escapeAttr(f.line) + '" ' +
                                'data-log-label="' + escapeAttr(f.name || '') + '" ' +
                                'title="' + escapeAttr(titleAttr) + '">' +
                                fileIcon('log-line') + ' ' + escapeAttr(f.name) +
                            '</span>' +
                            '<div class="agent-flow-file-desc">' + desc + '</div>' +
                        '</div>'
                    );
                }
                const titleAttr = f.note ? (f.note + ' — ' + f.path) : f.path;
                const rowClass  = 'agent-flow-file-row' + (f.isSpec ? ' is-spec' : '');
                return (
                    '<div class="' + rowClass + '">' +
                        '<span class="file-ref clickable" data-file-path="' + escapeAttr(f.path) + '" title="' + escapeAttr(titleAttr) + '">' +
                            fileIcon(f.kind) + ' ' + escapeAttr(f.name) +
                        '</span>' +
                        '<div class="agent-flow-file-desc">' + desc + '</div>' +
                    '</div>'
                );
            };

            // hideIfEmpty=true skips the section entirely when there are
            // no files, instead of rendering an "(none)" stub. Used for
            // Files Produced so dispatches with no outputs are silent.
            const renderSection = (label, files, hideIfEmpty) => {
                if (files.length === 0 && hideIfEmpty) return '';
                return (
                    '<div class="agent-flow-files-section">' +
                        '<div class="agent-flow-files-label">' + label + '</div>' +
                        (files.length === 0
                            ? '<div class="agent-flow-empty-files">(none)</div>'
                            : '<div class="agent-flow-files-rows">' + files.map(renderRow).join('') + '</div>') +
                    '</div>'
                );
            };

            return (
                '<li class="agent-flow-item" data-phase="' + phaseAttrVal + '">' +
                    '<div class="agent-flow-card">' +
                        '<h4 class="agent-flow-role">' + (entry.role || '') + '</h4>' +
                        (resolvedDesc
                            ? '<p class="agent-flow-agent-desc">' + resolvedDesc + '</p>'
                            : '') +
                        (entry.task
                            ? '<div class="agent-flow-task"><span class="agent-flow-task-label">Task</span>' + entry.task + '</div>'
                            : '') +
                        renderSection('Primary Files Referenced', loaded, false) +
                        renderSection('Primary Files Produced', produced, true) +
                    '</div>' +
                    '<div class="agent-flow-connector" data-phase="' + phaseAttrVal + '"></div>' +
                '</li>'
            );
        }).join('');
        return '<ol class="agent-flow">' + items + '</ol>';
    }

    // §§ BUILD_LEFT_PANEL (workflow cards: steps + checkpoints) ========
    function buildLeftPanel() {
        let currentPhase = 0;
        let stepCounter = 0;
        let checkpointCounter = 0;
        const fragment = document.createDocumentFragment();

        PIPELINE_STEPS.forEach((step, index) => {
            if (step.phase !== currentPhase) {
                currentPhase = step.phase;
                const meta = PHASE_METADATA.find(p => p.id === currentPhase);
                const header = document.createElement('div');
                header.className = 'phase-header';
                header.id = meta.sectionId;
                header.dataset.phase = String(currentPhase);
                header.innerHTML =
                    '<div class="phase-header-inner">' +
                      '<span class="phase-number">Phase ' + currentPhase + '</span>' +
                      '<span class="phase-title">' + meta.name + '</span>' +
                    '</div>' +
                    '<div class="phase-subtitle">' + meta.subtitle + '</div>';
                fragment.appendChild(header);
            }

            if (index > 0 && PIPELINE_STEPS[index - 1].phase === step.phase) {
                const connector = document.createElement('div');
                connector.className = 'step-connector';
                connector.dataset.phase = phaseAttr(step);
                fragment.appendChild(connector);
            }

            const card = step.type === 'checkpoint'
                ? buildCheckpointCard(step, ++checkpointCounter, index)
                : buildStepCard(step, ++stepCounter, index);
            card.dataset.index = index;
            card.dataset.phase = phaseAttr(step);
            card.setAttribute('tabindex', '0');
            card.setAttribute('role', 'article');
            stepElements.push(card);
            fragment.appendChild(card);
        });

        leftPanel.appendChild(fragment);
    }

    function buildStepCard(step, stepNum, index) {
        const card = document.createElement('div');
        card.className = 'step-card';
        card.id = step.id;
        card.setAttribute('aria-label', 'Step ' + stepNum + ' of 15: ' + step.title);

        const hasDetail = Array.isArray(step.agentFlow) && step.agentFlow.length > 0;

        // Per-step time placeholders. Real values can be set on each
        // PIPELINE_STEPS entry via `timeHuman` and `timeClaude` (any
        // string — "7 min", "~12m", "<1 min", etc). The defaults are
        // visible placeholders that the editor will replace.
        const timeHuman  = step.timeHuman  || '~5 min';
        const timeClaude = step.timeClaude || '~45 min';

        card.innerHTML =
            '<div class="step-card-top">' +
                '<span class="phase-tag">' + step.phaseName + '</span>' +
                '<span class="step-number">Step ' + stepNum + ' of 15</span>' +
                '<div class="step-time-badges" aria-label="Time spent on this step">' +
                    '<span class="time-badge human" title="Approximate human time spent on this step">' +
                        '<span class="time-badge-label">Human</span>' + escapeAttr(timeHuman) +
                    '</span>' +
                    '<span class="time-badge claude" title="Approximate Claude (AI) time spent on this step">' +
                        '<span class="time-badge-label">Claude</span>' + escapeAttr(timeClaude) +
                    '</span>' +
                '</div>' +
            '</div>' +
            '<h3 class="step-title">' + step.title + '</h3>' +
            '<p class="step-description">' + step.description + '</p>' +
            (hasDetail
                ? '<button class="expand-toggle" data-index="' + index + '" aria-expanded="false" aria-label="See how it works: ' + escapeAttr(step.title) + '"><span class="arrow">\u25B6</span> See how it works</button>' +
                  '<div class="step-detail" id="detail-' + index + '">' +
                    '<div class="step-detail-inner">' +
                        buildAgentFlow(step) +
                    '</div>' +
                  '</div>'
                : '');
        return card;
    }

    function buildCheckpointCard(step, cpNum, index) {
        const card = document.createElement('div');
        card.className = 'checkpoint-card';
        card.id = step.id;
        card.setAttribute('aria-label', 'Checkpoint ' + cpNum + ': ' + step.title);

        const reviewHTML = (step.reviewItems && step.reviewItems.length > 0)
            ? '<div class="checkpoint-review-label">Researcher reviews:</div>' +
              '<ul class="checkpoint-review-items">' + step.reviewItems.map(i => '<li>' + i + '</li>').join('') + '</ul>'
            : '';
        const actionsHTML = (step.researcherActions && step.researcherActions.length > 0)
            ? '<div class="checkpoint-actions-label">Researcher can:</div>' +
              '<ul class="checkpoint-actions">' + step.researcherActions.map(a => '<li>' + a + '</li>').join('') + '</ul>'
            : '';
        const refsHTML = (step.referencedFiles && step.referencedFiles.length > 0)
            ? '<div class="checkpoint-refs-label">Files to review:</div>' +
              '<div class="checkpoint-refs-list">' + step.referencedFiles.map(f => {
                  const nf = normalizeFile(f);
                  if (nf.kind === 'log-line') {
                      const titleAttr = nf.path + ':L' + nf.line;
                      return '<span class="file-ref clickable log-line-ref" ' +
                          'data-file-path="' + escapeAttr(nf.path) + '" ' +
                          'data-log-line="' + escapeAttr(nf.line) + '" ' +
                          'data-log-label="' + escapeAttr(nf.name || '') + '" ' +
                          'title="' + escapeAttr(titleAttr) + '">' +
                          fileIcon('log-line') + ' ' + escapeAttr(nf.name) + '</span>';
                  }
                  const title = nf.note ? (nf.note + ' — ' + nf.path) : nf.path;
                  return '<span class="file-ref clickable" data-file-path="' + escapeAttr(nf.path) + '" title="' + escapeAttr(title) + '">' +
                      fileIcon(nf.kind) + ' ' + escapeAttr(nf.name) + '</span>';
              }).join('') + '</div>'
            : '';

        const hasDetail =
            (step.reviewItems && step.reviewItems.length > 0) ||
            (step.researcherActions && step.researcherActions.length > 0) ||
            (step.referencedFiles && step.referencedFiles.length > 0);

        const timeHuman  = step.timeHuman  || '';
        const timeClaude = step.timeClaude || '';
        const timeBadges = (timeHuman || timeClaude)
            ? '<div class="step-time-badges" aria-label="Time spent on this checkpoint">' +
                  (timeHuman  ? '<span class="time-badge human" title="Approximate human time for this checkpoint"><span class="time-badge-label">Human</span>' + escapeAttr(timeHuman) + '</span>' : '') +
                  (timeClaude ? '<span class="time-badge claude" title="Approximate Claude (AI) time for this checkpoint"><span class="time-badge-label">Claude</span>' + escapeAttr(timeClaude) + '</span>' : '') +
              '</div>'
            : '';

        card.innerHTML =
            '<div class="step-card-top">' +
              '<span class="phase-tag">Checkpoint ' + cpNum + '</span>' +
              timeBadges +
            '</div>' +
            '<h3 class="checkpoint-title"><span class="checkpoint-icon"></span>' + step.title + '</h3>' +
            '<p class="checkpoint-description">' + step.description + '</p>' +
            (hasDetail
                ? '<button class="expand-toggle" data-index="' + index + '" aria-expanded="false" aria-label="See how it works: ' + escapeAttr(step.title) + '"><span class="arrow">\u25B6</span> See how it works</button>' +
                  '<div class="step-detail" id="detail-' + index + '">' +
                    '<div class="step-detail-inner checkpoint-detail-inner">' +
                        reviewHTML + actionsHTML + refsHTML +
                    '</div>' +
                  '</div>'
                : '') +
            (step.purposeQuote ? '<div class="human-gate"><span class="human-gate-icon">\u2716</span>DAAF will not proceed without explicit approval</div>' : '');

        return card;
    }

    // §§ UPDATE_RIGHT_PANEL ============================================
    // index === -1 → intro/report; -2 → next-steps/report (re-display);
    // index >= 0 → step content.
    // force=true bypasses the "same index" early-return so that clicking
    // the active card or collapsing a detail can re-seed the panel.
    //
    // Every step and every checkpoint in PIPELINE_STEPS carries an
    // `orchestratorLogLine: { path, line }` pointer into a real session
    // log file on GitHub (under LOG_DIR). When the card becomes active,
    // the panel shows a loading spinner, fires fetchLogLine(), and on
    // success swaps in buildLogMessageBodyHtml(obj). The fetch is async,
    // so the body is guarded by a `panelRenderToken` to prevent
    // late-arriving callbacks from clobbering newer state.
    // ================================================================
    function updateRightPanel(index, force) {
        if (index === activeStepIndex && !force) return;
        activeStepIndex = index;
        // Bump the render token so any in-flight async continuation
        // from the previous render sees a stale value and bails out.
        const token = ++panelRenderToken;
        // Any step change clears the viewing-badge highlight, since the right
        // panel is no longer showing a fetched document.
        clearViewingBadges();
        panelContent.classList.add('fading');

        setTimeout(() => {
            if (token !== panelRenderToken) return; // superseded
            // Both the intro zone (-1) and the next-steps zone (-2) show
            // the final report. They are tracked as distinct active
            // states so the nav highlight can switch between Overview
            // and the trailing section, but the right-panel content is
            // identical: a fresh buildReportFragment() render.
            if (index < 0) {
                updateMobilePill('View Analytic Report');
                panelTypeLabel.innerHTML =
                    '<a href="' + REPORT_BLOB_URL + '" target="_blank" rel="noopener" style="color:inherit;display:inline-flex;align-items:center;gap:0.5rem;">' +
                      'Initial Analytic Report <span class="report-badge">Main Output</span>' +
                    '</a>';
                panelTitle.textContent = 'College Graduation Rate & Selectivity Analysis';
                panelContent.innerHTML = '';
                panelContent.appendChild(buildReportFragment());
            } else {
                const step = PIPELINE_STEPS[index];
                if (step.type === 'checkpoint') {
                    panelTypeLabel.textContent = 'Checkpoint Review';
                    updateMobilePill('View Checkpoint', index);
                } else {
                    panelTypeLabel.textContent = 'Session Transcript';
                    updateMobilePill('View Transcript', index);
                }
                panelTitle.textContent = step.title;

                // Async fetch + render, guarded by token so a late
                // callback from a previous step can't clobber the
                // current view. `line` may be either a single number or
                // an array of numbers; arrays render as a stacked
                // `.log-message-group` with one card per line (each
                // card labelled "Message N of M · L<num>").
                if (step.orchestratorLogLine && step.orchestratorLogLine.path) {
                    const ll = step.orchestratorLogLine;
                    const linesRequested = Array.isArray(ll.line) ? ll.line : [ll.line];
                    const loadingLabel = linesRequested.length > 1
                        ? 'Loading ' + linesRequested.length + ' assistant messages\u2026'
                        : 'Loading assistant message\u2026';
                    panelContent.innerHTML =
                        '<div class="loading-state">' +
                            '<div class="loading-spinner"></div>' +
                            '<div class="loading-text">' + loadingLabel + '</div>' +
                        '</div>';
                    fetchLogLines(ll.path, linesRequested).then(objs => {
                        if (token !== panelRenderToken) return; // stale
                        const anyLoaded = objs.some(o => o);
                        if (!anyLoaded) {
                            panelContent.innerHTML =
                                '<div class="fetch-error">Could not load line' +
                                (linesRequested.length > 1 ? 's ' : ' ') +
                                escapeAttr(linesRequested.join(', ')) +
                                ' from <code>' + escapeAttr(ll.path) + '</code>.</div>';
                            return;
                        }
                        const transcriptLink = logTranscriptLinkHtml(ll.path);
                        if (objs.length === 1) {
                            panelContent.innerHTML = transcriptLink + buildLogMessageBodyHtml(objs[0]);
                            return;
                        }
                        // Multi-line group render: one .log-message card
                        // per requested line, wrapped in a flex container
                        // with a teal-to-indigo pipeline rail. Only the
                        // first card shows the "DAAF Assistant Message
                        // Logs" header — subsequent cards are headerless
                        // so the group reads as one continuous thread.
                        const cards = objs.map((obj, i) => {
                            const hideHeader = i > 0;
                            if (!obj) {
                                const headerHtml = hideHeader
                                    ? ''
                                    : ('<div class="log-message-header">' +
                                           '<span class="log-message-role">DAAF Assistant Message Logs</span>' +
                                       '</div>');
                                return (
                                    '<div class="log-message log-message-missing">' +
                                        headerHtml +
                                        '<div class="log-message-body"><p><em>Could not load line ' + escapeAttr(String(linesRequested[i])) + '.</em></p></div>' +
                                    '</div>'
                                );
                            }
                            return buildLogMessageBodyHtml(obj, hideHeader);
                        }).join('');
                        panelContent.innerHTML = transcriptLink + '<div class="log-message-group">' + cards + '</div>';
                    });
                } else {
                    panelContent.innerHTML =
                        '<div class="fetch-error">No transcript reference available for this step.</div>';
                }
            }
            referencePanel.scrollTop = 0;
            panelContent.classList.remove('fading');
        }, FADE_MS);
    }

    // §§ ACTIVE_STEP ===================================================
    // Step cards and checkpoints inherit their phase color from the CSS
    // cascade ([data-phase] rules), so this just flips aria-current.
    // ================================================================
    function setActiveStep(index, force) {
        stepElements.forEach((el, i) => {
            if (i === index) el.setAttribute('aria-current', 'step');
            else el.removeAttribute('aria-current');
        });
        updateRightPanel(index, force);
        updateNavHighlight(index);
        updateProgressRail(index);
        updateMobileProgress(index);
    }

    function updateNavHighlight(index) {
        // Clear only the section-nav dropdown links (those with data-section),
        // not Learn subpage links or other dropdown items.
        const dropdownLinks = document.querySelectorAll('.nav-dropdown-menu a[data-section]');
        dropdownLinks.forEach(link => link.classList.remove('active'));
        // Keep "See How It Works" parent always active on this page
        const parentLink = document.querySelector('.nav-links .nav-dropdown .nav-dropdown-toggle');
        if (parentLink) parentLink.classList.add('active');
        // -2 → Next Steps; -1 → Overview; 0..n → the card's phase tab.
        if (index === -2) {
            const nextLink = document.querySelector('.nav-dropdown-menu a[data-section="next-steps"]');
            if (nextLink) nextLink.classList.add('active');
            return;
        }
        if (index < 0) {
            const overviewLink = document.querySelector('.nav-dropdown-menu a[data-section="intro"]');
            if (overviewLink) overviewLink.classList.add('active');
            return;
        }
        const step = PIPELINE_STEPS[index];
        const link = document.querySelector('.nav-dropdown-menu a[data-section="phase-' + step.phase + '"]');
        if (link) link.classList.add('active');
    }

    // §§ SCROLL_OBSERVER ===============================================
    // Single source of truth: one debounced scroll listener resolves
    // the active index for both intro (-1) and step cards (0..n).
    //
    // Algorithm: walk step elements in document order, track the last
    // one whose top has crossed the focus line. This is height-
    // independent and monotonic — when a user expands a long Read More
    // the card's top doesn't move, so the active index doesn't
    // accidentally switch. When scrolling deep inside a tall expanded
    // card, rect.top stays negative → `best` stays on that card. When
    // the next card's top finally crosses the focus line going down,
    // transition happens correctly.
    // ================================================================
    function findActiveCard() {
        const focusLine = window.innerHeight * FOCUS_LINE_RATIO;
        // Next-steps zone is checked first: once its top has crossed
        // the focus line, we are past the workflow regardless of which
        // step element is technically the "last crossed" one. -2 is
        // the sentinel index, mirroring the -1 sentinel for intro.
        if (nextStepsSection && nextStepsSection.getBoundingClientRect().top <= focusLine) {
            return -2;
        }
        let best = null;
        for (let i = 0; i < stepElements.length; i++) {
            if (stepElements[i].getBoundingClientRect().top <= focusLine) best = i;
            else break;
        }
        if (best === null && stepElements.length > 0) {
            const firstCardTop = stepElements[0].getBoundingClientRect().top;
            if (firstCardTop > focusLine) return -1;
        }
        return best === null ? -1 : best;
    }

    function setupScrollObserver() {
        let scrollDebounceTimer = null;

        window.addEventListener('scroll', () => {
            if (scrollDebounceTimer) clearTimeout(scrollDebounceTimer);
            scrollDebounceTimer = setTimeout(() => {
                if (lockScrollObserver) return;
                const best = findActiveCard();
                if (best !== activeStepIndex) setActiveStep(best);
            }, SCROLL_DEBOUNCE);
        }, { passive: true });

        // Rail visibility — show the progress rail only when the workflow
        // section is actually in view. This is independent of active-step
        // resolution, so the observer is safe to keep.
        const progressRail = document.getElementById('progress-rail');
        const workflowSection = document.getElementById('workflow');
        const railObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                progressRail.classList.toggle('visible', entry.isIntersecting);
            });
        }, { rootMargin: '-88px 0px 0px 0px' });
        railObserver.observe(workflowSection);
    }

    // §§ KEYBOARD_NAV ================================================== */
    function setupKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            switch (e.key) {
                case 'Escape':
                    if (mobileSheetOpen) { closeMobileSheet(); e.preventDefault(); }
                    break;
                case 'ArrowDown': case 'j':
                    e.preventDefault();
                    navigateStep(1);
                    break;
                case 'ArrowUp': case 'k':
                    e.preventDefault();
                    navigateStep(-1);
                    break;
                case ' ': case 'Enter':
                    if (activeStepIndex != null && activeStepIndex >= 0) {
                        e.preventDefault();
                        toggleDetail(activeStepIndex);
                    }
                    break;
                case 'Home':
                    e.preventDefault();
                    document.getElementById('intro').scrollIntoView({ behavior: 'smooth' });
                    break;
                case 'End':
                    e.preventDefault();
                    if (stepElements.length > 0) {
                        stepElements[stepElements.length - 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    break;
            }
        });
    }

    function navigateStep(direction) {
        const baseIndex = activeStepIndex == null ? -1 : activeStepIndex;
        const newIndex = Math.max(-1, Math.min(stepElements.length - 1, baseIndex + direction));
        if (newIndex === -1) {
            document.getElementById('intro').scrollIntoView({ behavior: 'smooth' });
        } else if (newIndex >= 0 && newIndex < stepElements.length) {
            scrollToStepTop(stepElements[newIndex]);
        }
    }

    function scrollToStepTop(targetCard) {
        const targetTop = targetCard.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({ top: targetTop - scrollHeaderOffset() - 24, behavior: 'smooth' });
    }

    function toggleDetail(index) {
        const card = stepElements[index];
        const detail = card.querySelector('.step-detail');
        const toggle = card.querySelector('.expand-toggle');
        if (!detail) return;
        const wasExpanded = detail.classList.contains('expanded');
        detail.classList.toggle('expanded');
        if (toggle) {
            toggle.classList.toggle('open', !wasExpanded);
            toggle.setAttribute('aria-expanded', String(!wasExpanded));
        }
        // If we just collapsed, reset the right panel to the orch excerpt
        // (in case the user had a fetched document showing).
        if (wasExpanded) {
            updateRightPanel(index, true);
        }
    }

    // §§ VIEWING_BADGES ================================================
    // The badge whose document is currently displayed in the right panel
    // gets a .viewing class. Cleared whenever the active step changes.
    // ================================================================
    function clearViewingBadges() {
        document.querySelectorAll('.file-ref.viewing')
            .forEach(b => b.classList.remove('viewing'));
    }
    function markViewingBadge(badge) {
        clearViewingBadges();
        if (badge) badge.classList.add('viewing');
    }

    // §§ MOBILE_SHEET ===================================================
    // Bottom sheet pattern for ≤900px: the right-column element is
    // restyled by CSS as a fixed overlay that slides up from the bottom.
    // These functions toggle the .sheet-open class and manage the
    // backdrop, pill visibility, and body scroll lock.
    // ================================================================
    function openMobileSheet() {
        if (!mobileQuery.matches || mobileSheetOpen) return;
        mobileSheetOpen = true;
        // Compensate for scrollbar disappearance to prevent layout shift
        const scrollbarW = window.innerWidth - document.documentElement.clientWidth;
        if (scrollbarW > 0) document.body.style.paddingRight = scrollbarW + 'px';
        referencePanel.classList.add('sheet-open');
        mobileBackdrop.classList.add('active');
        if (mobilePill) mobilePill.classList.add('hidden');
        document.body.style.overflow = 'hidden';
    }
    function closeMobileSheet() {
        if (!mobileSheetOpen) return;
        mobileSheetOpen = false;
        referencePanel.classList.remove('sheet-open');
        mobileBackdrop.classList.remove('active');
        if (mobilePill) mobilePill.classList.remove('hidden');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }
    function updateMobilePill(label, index) {
        if (!mobilePillLabel) return;
        let text = label || 'View Reference';
        if (index != null && index >= 0) {
            text = 'Part ' + (index + 1) + '/' + PIPELINE_STEPS.length + ' \u00b7 ' + text;
        }
        mobilePillLabel.textContent = text;
        // Pulse the pill to signal new content (only when sheet is closed)
        if (!mobileSheetOpen && mobileQuery.matches && mobilePill) {
            mobilePill.classList.remove('pulse');
            void mobilePill.offsetWidth; // reflow to restart animation
            mobilePill.classList.add('pulse');
        }
    }
    function setupMobileSheet() {
        if (mobilePill) {
            mobilePill.addEventListener('click', () => {
                if (mobileSheetOpen) closeMobileSheet();
                else openMobileSheet();
            });
        }
        if (mobileBackdrop) {
            mobileBackdrop.addEventListener('click', closeMobileSheet);
        }
        const closeBtn = document.getElementById('panel-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeMobileSheet);
        }
        // Auto-close bottom sheet when viewport grows past mobile breakpoint
        mobileQuery.addEventListener('change', (e) => {
            if (!e.matches && mobileSheetOpen) closeMobileSheet();
        });
    }

    // §§ MOBILE_PROGRESS ================================================
    // Horizontal phase bar shown below nav on mobile. 5 tappable
    // segments (one per phase) with phase colors; active segment is
    // full opacity, past segments semi-transparent, future segments dim.
    // ================================================================
    function buildMobileProgress() {
        const bar = document.getElementById('mobile-progress');
        if (!bar) return;
        const shortNames = { 1: 'Discovery', 2: 'Planning', 3: 'Data Acq.', 4: 'Analysis', 5: 'Synthesis' };
        PHASE_METADATA.forEach(meta => {
            const seg = document.createElement('div');
            seg.className = 'mobile-progress-segment';
            seg.dataset.phase = String(meta.id);
            seg.title = meta.name;
            const label = document.createElement('span');
            label.className = 'mobile-progress-label';
            label.textContent = shortNames[meta.id] || meta.name;
            seg.appendChild(label);
            seg.addEventListener('click', () => {
                const header = document.getElementById(meta.sectionId);
                if (header) {
                    const top = header.getBoundingClientRect().top + window.scrollY - scrollHeaderOffset() - 10;
                    window.scrollTo({ top, behavior: 'smooth' });
                }
            });
            bar.appendChild(seg);
        });
    }
    function updateMobileProgress(index) {
        const segments = document.querySelectorAll('.mobile-progress-segment');
        if (!segments.length) return;
        if (index < 0) {
            segments.forEach(s => s.classList.remove('active', 'past'));
            return;
        }
        const activePhase = PIPELINE_STEPS[index].phase;
        segments.forEach(seg => {
            const p = parseInt(seg.dataset.phase, 10);
            seg.classList.toggle('active', p === activePhase);
            seg.classList.toggle('past', p < activePhase);
        });
    }

    // §§ EVENT_LISTENERS (delegated clicks + nav + keyboard wiring) ===
    function setupEventListeners() {
        leftPanel.addEventListener('click', (e) => {
            const toggle = e.target.closest('.expand-toggle');
            if (toggle) {
                e.stopPropagation();
                toggleDetail(parseInt(toggle.dataset.index, 10));
                return;
            }

            // (f) Row-level click forwarding: if the user clicked
            // anywhere inside an .agent-flow-file-row that isn't the
            // file-ref itself, forward the click to the contained
            // file-ref so the whole row acts as a single click target.
            // This keeps all downstream logic (image short-circuit,
            // viewing-badge marking, fetch/render) in one code path.
            const fileRow = e.target.closest('.agent-flow-file-row');
            let fileRef = e.target.closest('.file-ref');
            if (fileRow && !fileRef) {
                fileRef = fileRow.querySelector('.file-ref');
            }
            if (fileRef) {
                e.stopPropagation();
                const filePath = fileRef.dataset.filePath;
                if (filePath) {
                    markViewingBadge(fileRef);
                    // Log-line refs route through fetchLogLine() — the
                    // path is a repo-relative URL to a JSONL session
                    // log on GitHub, and the line number identifies
                    // which record to extract and render. The full
                    // file is cached after the first fetch, so
                    // subsequent line lookups are free.
                    if (fileRef.classList.contains('log-line-ref')) {
                        const logLine = parseInt(fileRef.dataset.logLine, 10);
                        const logLabel = fileRef.dataset.logLabel || fileRef.textContent.trim();
                        showLoadingState();
                        if (mobileQuery.matches) openMobileSheet();
                        fetchLogLine(filePath, logLine).then(obj => {
                            if (obj) {
                                renderLogMessageInPanel(obj, filePath, logLine, logLabel);
                                updateMobilePill('View Log');
                            } else {
                                panelTypeLabel.textContent = 'Error';
                                panelTitle.textContent = filePath.split('/').pop() + ' · L' + logLine;
                                panelContent.innerHTML = '<div class="fetch-error">' +
                                    'Could not load log line ' + logLine + ' from <code>' + escapeAttr(filePath) + '</code>.' +
                                    '<br><br>Verify the file exists in the DAAF repo at this path ' +
                                    'and that the line number is within range.</div>';
                            }
                        });
                        return;
                    }
                    // (e fix) Image files must NEVER hit fetchDocument —
                    // response.text() on binary data produces megabytes of
                    // garbage that hang the browser before rendering as
                    // gibberish. Render images directly as <img> tags
                    // pointing at the GitHub raw URL.
                    if (isImagePath(filePath)) {
                        renderImageInPanel(filePath, fileRef.textContent.trim());
                        updateMobilePill('View Figure');
                        if (mobileQuery.matches) openMobileSheet();
                        return;
                    }
                    if (mobileQuery.matches) openMobileSheet();
                    fetchDocument(filePath).then(content => {
                        if (content) {
                            renderDocumentInPanel(filePath, content, fileRef.textContent.trim());
                            updateMobilePill('View Document');
                        } else {
                            panelTypeLabel.textContent = 'Error';
                            panelTitle.textContent = filePath.split('/').pop();
                            panelContent.innerHTML = '<div class="fetch-error">Failed to load: ' + filePath +
                                '<br><br><a href="' + GITHUB_BLOB_BASE + filePath + '" target="_blank" rel="noopener">View on GitHub \u2197</a></div>';
                        }
                    });
                }
                return;
            }

            const card = e.target.closest('.step-card, .checkpoint-card');
            if (card && card.dataset.index !== undefined) {
                setActiveStep(parseInt(card.dataset.index, 10), true);
                if (mobileQuery.matches) openMobileSheet();
            }
        });

        // Dropdown section links — smooth scroll within this page.
        // Only intercept links inside the dropdown menu that have
        // data-section attrs (anchor hrefs to sections on this page).
        // Other dropdown links (Learn subpages, Blog, etc.) navigate normally.
        document.querySelectorAll('.nav-dropdown-menu a[data-section]').forEach(navLink => {
            navLink.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = navLink.getAttribute('href').slice(1);
                const target = document.getElementById(targetId);
                if (target) {
                    if (targetId === 'intro') {
                        lockScrollObserver = true;
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                        setActiveStep(-1);
                        setTimeout(() => { lockScrollObserver = false; }, NAV_LOCK_MS);
                    } else if (targetId === 'next-steps') {
                        lockScrollObserver = true;
                        const top = target.getBoundingClientRect().top + window.scrollY - scrollHeaderOffset() - 20;
                        window.scrollTo({ top, behavior: 'smooth' });
                        setActiveStep(-2);
                        setTimeout(() => { lockScrollObserver = false; }, NAV_LOCK_MS);
                    } else {
                        const top = target.getBoundingClientRect().top + window.scrollY - scrollHeaderOffset() - 20;
                        window.scrollTo({ top, behavior: 'smooth' });
                    }
                }
                document.getElementById('nav-links').classList.remove('open');
                document.querySelector('.nav-toggle').setAttribute('aria-expanded', 'false');
                // Also close any open dropdowns
                document.querySelectorAll('.nav-dropdown.mobile-open').forEach(function(dd) {
                    dd.classList.remove('mobile-open');
                    var btn = dd.querySelector('.nav-dropdown-toggle');
                    if (btn) btn.setAttribute('aria-expanded', 'false');
                });
            });
        });

        // "See How It Works" parent button — scroll to intro on desktop,
        // expand/collapse dropdown on mobile.
        const dropdownParent = document.querySelector('.nav-links .nav-dropdown .nav-dropdown-toggle');
        if (dropdownParent) {
            dropdownParent.addEventListener('click', (e) => {
                if (mobileQuery.matches) {
                    // On mobile: toggle expand/collapse instead of scrolling
                    var dropdown = dropdownParent.closest('.nav-dropdown');
                    dropdown.classList.toggle('mobile-open');
                    dropdownParent.setAttribute('aria-expanded', dropdown.classList.contains('mobile-open'));
                    return;
                }
                e.preventDefault();
                lockScrollObserver = true;
                window.scrollTo({ top: 0, behavior: 'smooth' });
                setActiveStep(-1);
                setTimeout(() => { lockScrollObserver = false; }, NAV_LOCK_MS);
                document.getElementById('nav-links').classList.remove('open');
                document.querySelector('.nav-toggle').setAttribute('aria-expanded', 'false');
            });
        }

        // Mobile dropdown expand/collapse for all OTHER dropdown toggles
        // (the first one is handled above with special scroll-to-intro logic)
        document.querySelectorAll('.nav-dropdown-toggle').forEach(function(btn) {
            if (btn === dropdownParent) return; // skip — handled above
            btn.addEventListener('click', function() {
                var dropdown = btn.closest('.nav-dropdown');
                dropdown.classList.toggle('mobile-open');
                btn.setAttribute('aria-expanded', dropdown.classList.contains('mobile-open'));
            });
        });

        document.getElementById('begin-walkthrough').addEventListener('click', () => {
            const phaseHeader = document.getElementById('phase-1') || document.querySelector('.phase-header');
            if (phaseHeader) {
                const top = phaseHeader.getBoundingClientRect().top + window.scrollY - scrollHeaderOffset() - 20;
                window.scrollTo({ top, behavior: 'smooth' });
            }
        });

        document.querySelector('.nav-toggle').addEventListener('click', () => {
            const navLinks = document.getElementById('nav-links');
            const isOpen = navLinks.classList.toggle('open');
            document.querySelector('.nav-toggle').setAttribute('aria-expanded', String(isOpen));
            // When closing the nav, also close any open dropdowns
            if (!isOpen) {
                document.querySelectorAll('.nav-dropdown.mobile-open').forEach(function(dd) {
                    dd.classList.remove('mobile-open');
                    var btn = dd.querySelector('.nav-dropdown-toggle');
                    if (btn) btn.setAttribute('aria-expanded', 'false');
                });
            }
        });
    }

    // §§ INIT ========================================================== */
    function init() {
        leftPanel        = document.getElementById('workflow');
        panelContent     = document.getElementById('panel-content');
        panelTypeLabel   = document.getElementById('panel-type-label');
        panelTitle       = document.getElementById('panel-title');
        referencePanel   = document.getElementById('reference-panel');
        nextStepsSection = document.getElementById('next-steps');
        mobilePill       = document.getElementById('mobile-panel-pill');
        mobileBackdrop   = document.getElementById('mobile-backdrop');
        mobilePillLabel  = document.getElementById('mobile-pill-label');

        buildProgressRail();
        buildMobileProgress();
        buildLeftPanel();
        setupEventListeners();
        setupKeyboardNav();
        setupMobileSheet();

        // Initial render: check the URL hash to determine the starting
        // section. Hash values map to either special zones (-1 for intro,
        // -2 for next-steps) or the first step index of a phase.
        var initialIndex = -1;
        var hash = window.location.hash.slice(1);
        if (hash === 'next-steps') {
            initialIndex = -2;
        } else if (hash && hash !== 'intro') {
            // Map phase hashes (e.g. "phase-3") to the first PIPELINE_STEPS
            // index that belongs to that phase, so the right panel loads
            // the correct transcript instead of the default report.
            var phaseMatch = hash.match(/^phase-(\d+)$/);
            if (phaseMatch) {
                var targetPhase = parseInt(phaseMatch[1], 10);
                for (var si = 0; si < PIPELINE_STEPS.length; si++) {
                    if (PIPELINE_STEPS[si].phase === targetPhase) {
                        initialIndex = si;
                        break;
                    }
                }
            }
        }
        setActiveStep(initialIndex, true);

        requestAnimationFrame(setupScrollObserver);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
