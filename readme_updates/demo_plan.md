Demo outline:
Slide 1:
LLM-based AI assistants are becoming increasingly capable, but they also are always at risk of:
(fade in each of these in rhythm)
- Hallucination
- Sycophancy
- Over-confidence
- Laziness

Slide up the previous text and reveal:
...which means every time you use an LLM, you are rolling the dice. Can these flawed and non-deterministic tools still be useful for conducting rigorous data analysis for the sciences? 

Yes! (fade in insert HUGE asterisk here)

Slide up the previous text and reveal:
(insert asterisk here) but **only** with the **right guidance**, **right guardrails** and in **expert hands** to guide all core decisions and verify all key outputs

Enter:
(Insert the DAAF logo reveal here)
v2.0.0

DAAF is an open-source (^read: **forever** free!) instructions framework that sits between you and Claude Code to automatically and consistently help Claude think more like a responsible and rigorous researcher by: (scroll through each of these in order)
- Enforcing strict auditability and reproducibility standards at all stages of work -> Verify, don't trust
- Preventing potentially dangerous unintended file access and editing -> Sandboxed with heavy permission restrictions
- Embedding high standards of care and rigor and thoroughness for all data analysis work -> Taught to comment, verify, and review all analytic code every step of the way
- Embedding knowledge on best practices for causal inference, geospatial analysis, survey methodology, science communication, data visualization, and more -> Rich agent Skills that extend Claude's capabilities, informed by **real** papers, guides, tutorials, and resources. Many more on the way!
- Collaborating with you directly on all key decisions -> Keep the expert human firmly in the driver's seat

(Scroll over to this)
Think of DAAF like a **force-multiplying exoskeleton** for human researchers -- a tool that is explicitly designed to **augment** your hard-earned expertise and skills, rather than replace them. The goal is that DAAF makes it **easy** for researchers to use Claude Code effectively **and** responsibly.

Install and start your work with Claude+DAAF in just ten minutes from a completely fresh computer with a high-usage Anthropic account (display the full set of install lines).

Once you're in? Ask it for whatever. DAAF intelligently responds to your needs by automatically selecting and walking you through a variety of bespoke research workflow modes:
(for each mode, begin by showing a representative query being typed out by the user. Use an interface that looks like a mac terminal and reference the Claude Code screenshot /workspace/content_refs/DAAF_v2_references/claude_code_screenshot.png. Then show the Mode and description like a hero title. Off to the left you reveal what you do, then what DAAF does, then show the thinking animation for Claude, then show what you get, then show the representative response from Claude to the representative user query)
- Data Onboarding Mode: Make Claude an expert in **your** data
	- What you do: Point DAAF to your data (local, web download, or API access) and any associated documentation/codebooks. 
	- What DAAF does: Runs a multi-stage data profiling process to learn all the ins-and-outs (with fully reproducible code) alongside any provided documentation
	- What you get: An in-depth data documentation reference Skill that DAAF can use to inform any and all work it does with your data from here on. Fully portable, share with colleagues and collaborators!
- Data Lookup Mode: Your personal data documentation oracle
	- What you do: Ask DAAF a specific question about any given dataset it has access to
	- What DAAF does: Loads up the data documentation Skill and pores over all relevant reference information in seconds
	- What you get: A precise, documentation-informed answer to your question with opportunities to dig in further
- Data Discovery Mode: Connect the dots between multiple data sources and topics
	- What you do: Ask DAAF a broad data or research scoping question
	- What DAAF does: Launches a series of data documentation explorations into any and all  data available to it as relevant to your question
	- What you get: An in-depth summary of relevant opportunities, insights, clarifications, and caveats to consider in formulating your next steps for research in this direction
- Ad Hoc Collaboration Mode: Rapidly co-develop research ideas, methodological strategies, analytic scripts, and more
	- What you do: Ask DAAF to help you riff on anything research-related
	- What DAAF does: Engages you as a collaborator with its embedded domain and methodological expertise guiding the way
	- What you get: A much smarter, more grounded, and more helpful Claude assistant
- Full Pipeline Mode: From research question to results with your guidance and input every step of the way
	- What you do: Ask DAAF for support answering any arbitrarily complex research question with your data
	- What DAAF does: Data scoping, analytic/methodological planning, data pulling/cleaning/analysis, in-depth code review, data visualization, and summary report writing -- the works
	- What you get: An in-depth pre-analysis plan, a fully reproducible end-to-end analysis for your close review, and a summary report with key findings, data visualizations, limitations, citations, and learnings for future work
- Revision and Extension Mode: Make DAAF's first draft better and 
	- What you do: Ask for revisions or new deliverables related to any prior analysis
	- What DAAF does: Reviews the prior analysis and launches revisions, reruns analyses as needed, updates all downstream work, builds beyond.
	- What you get: Refined analyses, or any new dashboards, visualizations, stakeholder reports you can think of
- Reproducibility Verification Mode: Verify, don't trust
	- What you do: Point DAAF to a full pipeline analysis produced by yourself or others
	- What DAAF does: Reruns and reverifies every single script against the final report to be reviewed, critiquing and exploring along the way
	- What you get: An in-depth reproducibility report with issues, concerns, opportunities, and summary takeaways
- Framework Development Mode: Make DAAF work for **you**
	- What you do: Ask DAAF to improve its functionality: new methodologies, new Python libraries, new domain expertise, or new modes entirely
	- What DAAF does: Pores over its own architecture, conducts in-depth research online, and meticulously updates its own functionality
	- What you get: A better DAAF with modular skills and agents that you can share back with colleagues or the community writ large

Many, many more features and supported research approaches than can reasonably be mentioned here
(display the title text on the left side, and on the right side, display a rapidly populating set of badges listing each of the following):
- 40+ Urban Institute Education Data Portals included out of the box:
	- CCD, CRDC, EdFacts, FSA, IPEDS, MEPS, NACUBO, NHGIS, PSEO, SAIPE, College Scorecard, NCCS
- Methodological support:
	- Difference-in-differences designs
	- Fixed effects and random effects
	- Propensity score matching/weighting
	- Event studies
	- Instrumental variables
	- Synthetic control
	- Time series analysis
	- Regression discontinuity designs
	- Randomized controlled trial analyses
	- Survey response weighting
	- Geospatial processing
	- Geospatial analysis
	- Decomposition analysis
	- Exploratory data analysis
	- Directed Acyclic Graph modeling
	- Predictive analytics
	- Cross-validation approaches
	- Algorithmic fairness assessment
	- Cluster analysis
- Interactive dashboard creation via Plotly
- Git version control
- Interactive analytic notebooks via Marimo
- Science-communication best practices
- R/tidyverse analytic translation support
- Stata analytic translation support
- Python library expertise:
	- linearmodels pyfixest polars plotly plotnine geopandas marimo scikit-learn statsmodels svy

And this is just the beginning. Much, much more to come!

LLMs will always be susceptible to hallucination, sycophancy, over-confidence, and laziness, but with the right guidance, guardrails, and in **expert hands**, they can still be enormously useful for advancing and accelerating good science.

Get started using DAAF with a high-usage Anthropic account in 10 minutes here: 
https://github.com/DAAF-Contribution-Community/daaf
plus QR code daaf-repo-qr-code.jpg

(Put in smaller text below with Open Augments logo) DAAF is free and always will be as the flagship project of Open Augments
https://openaugments.org/
