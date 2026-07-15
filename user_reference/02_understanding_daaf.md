# 02. Understanding and Working with DAAF

This guide is designed to turn a new user into a confident user. It expands on the README and installation guide's brief overview into a thorough walkthrough of how DAAF works, what it produces, what to expect, where it can fail, and how to think about AI-assisted research analysis for your workflows more critically. This will guide you through your first real analysis with DAAF to understand what's happening under the hood, and suggest further testing pathways to really get comfortable with the strengths and weaknesses of DAAF.

> **Quick tip before you begin**: If you have any questions, concerns, issues, or confusion about **anything** you read in this guide: Ask Claude for help! Point it to any document, section, or sentence, and then ask it to help you understand it better. It has visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**What is DAAF?**](#what-is-daaf)
- [**How LLMs Actually Work**](#how-llms-actually-work)
- [**Three Dimensions of AI Capability**](#three-dimensions-of-ai-capability)
- [**From Intuition to Design: The Three Challenges**](#from-intuition-to-design-the-three-challenges)
- [**The Mental Model: Orchestrator, Agents, Skills**](#the-mental-model-orchestrator-agents-skills)
- [**The Nine Engagement Modes**](#the-nine-engagement-modes)
- [**Easing in with Progressively More Advanced Queries**](#easing-in-with-progressively-more-advanced-queries)
- [**Anatomy of a Completed Analysis**](#anatomy-of-a-completed-analysis)
- [**Looking at the Sample Projects**](#looking-at-the-sample-projects)
- [**Dual-Layer Validation**](#dual-layer-validation)
- [**Session Management: Multi-Session Work and Recovery**](#session-management-multi-session-work-and-recovery)
- [**Where Things Live in the Repository**](#where-things-live-in-the-repository)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## What is DAAF?

DAAF is an AI-powered research assistant that helps you go from a research question to a completed analysis (including data acquisition, cleaning, statistical analysis, visualizations, and a written report) while keeping you in control of every decision. It runs inside a tool called Claude Code (Anthropic's AI coding assistant) on your computer. You interact with it by typing instructions in plain English, and DAAF handles the technical work while checking in with you at key decision points. Claude Code is a powerful general-purpose AI coding assistant, but it wasn't designed specifically for research: DAAF adds the structure, the domain knowledge, and the safety guardrails that turn it into a rigorous research tool.

Ignoring the fancy terms for a moment (agents, subagents, skills, orchestrators) -- DAAF is just a series of pre-cooked "recipes" of context that get handed to Claude at exactly the right moments. Every single design decision in DAAF comes down to telling Claude exactly what it needs to know, when it needs to know it, so it does what you want more often and with higher quality on average -- transparently and rigorously and reproducibly, like a scientist would prefer. Anyone can put this together without DAAF in simpler ways or just ad-hoc (i.e., by writing a single very long, custom prompt to regular Claude Code) -- I'm just trying to make it easier for people with sensible defaults and opinionated standards of rigor.

Why that works, and why it matters so much, becomes much clearer once you understand how these AI systems actually operate under the hood. So that's where we'll start. You need to know this before you do anything else with DAAF, because it will fundamentally shape how you use and interact with it, as well as what you should expect from it.

---

## How LLMs Actually Work

Every large language model (LLM) assistant (e.g., Claude, ChatGPT, Gemini) is, at its core, an autocomplete engine. It takes a sequence of words and tries to come up with the next best, most sensical word in that sequence -- then the next, then the next. I like to describe modern AI as **autocomplete with an extremely fancy hat**: the hat keeps getting fancier, but the mechanic underneath hasn't changed. Everything crazy you've seen an AI do like writing code, building slide decks, and searching the web, all fundamentally stems from this one simple but extremely flexible mechanic.

That mechanic is also the technology's fundamental flaw. Predicting the next plausible word is not a process grounded in truth or correctness. When an LLM gets something wrong and **"hallucinates,"** it isn't malfunctioning: it's just making stuff up the way it always does, predicting a word that happens to imply an untruth or an unfact. To see how this works (and why there's still real hope for making these tools useful), take a sequence of words:

> *"My favorite food is ___?"*

With minimal context, the model's candidate next words might look something like this:

| Candidate next word | Illustrative probability |
|---------------------|--------------------------|
| pizza | 32% |
| sushi | 11% |
| chocolate | 9% |
| pasta | 8% |
| *-- sampling threshold --* | |
| tacos | 4% |
| acorns | 0.1% |

*(Note: Fake data/example for illustration purposes only!)*

The model turns the words it's given into mathematical points in space and uses complex math to predict the next word (to wildly oversimplify, you can almost imagine it plots a sort of best-fit prediction/regression line) then picks somewhat randomly among the top candidates above the threshold of likelihood.

That random selection among top candidates is intentional, by the way: model providers add it deliberately to produce variety and something resembling creativity. But it also means the same question can get different answers on different days: pizza today, cheese next week, ice cream tomorrow. It'll also change based on exactly how we phrase the question itself. If we're asking these systems for anything factual or truth-based, we are going to be disappointed.

### Two Kinds of "Memory"

So if these systems aren't grounded in truth, how could they possibly be useful for science -- which requires truth and fact and rigor and care? Here's a mental model that helps (it's not the most accurate technical description, but it's a substantively useful one): an LLM almost draws on **two kinds of "memory"** when it fills in that blank.

Its **long-term memory** is the training data -- any given LLM model "reads" essentially every publicly available book, code repository, Wikipedia article, and Reddit thread to form a baked-in, fuzzy understanding of language and the world when it is first created. When a model relies solely on this long-term memory, it's piecing together a bunch of fuzzy information all at once without really getting any of it quite right -- it will confidently make stuff up, and it will often be wrong in the details. You can imagine at least in part because it has so much data to influence it, and because a lot of that information may conflict. Its **short-term memory** is information that is provided directly to it in something called the **context window** -- the instructions, documents, and conversation you provide directly, sitting presently in its "mind" as you chat with it. When the model works from material in its short-term memory, its informational recall and specific topical synthesis are far more precise and far more useful.

| | "Long-term" memory | "Short-term" memory |
|---|---------------------|----------------------|
| **What it is** | Training data baked into the model | Context you provide in the moment (the context window) |
| **What's in it** | Wikipedia articles, Reddit threads, books & papers, forum posts, code repositories, news articles, social media, textbooks, blog posts | Your instructions & system prompt, your data & documents, your conversation history, examples & reference material |
| **Character** | Broad, approximate, imprecise | Specific, curated, deliberate |
| **Reliability** | Fuzzy informational recall, weaker synthesis | Far more precise recall and synthesis |

> The reliability comparison here is directional, not measured -- the point is the gap. Working from curated short-term memory is far more reliable than recalling from fuzzy long-term memory, though neither is ever guaranteed.

The practical implication: whenever we can shift an LLM's work from relying on its long-term memory to instead relying on what we carefully curate and provide directly to it in its short-term memory, we get a lot better performance out of it, and it becomes much, much more useful. To see what that looks like, return to our "favorite food" sentence from earlier: this time with a rich paragraph of context placed directly into the model's short-term memory:

> *"Janice loves pizza more than anyone I've ever known. It's bizarre; every time I suggest we get food, she without fail suggests one of the twenty random pizza shops in town. Me? I've always hated the fact that people find ways to enjoy the simple things. Life is meant to be nuanced, complex, novel. Simple things are boring, and simple things are by definition plain.*
>
> *My favorite food is ___?"*

| Candidate next word | Illustrative probability |
|---------------------|--------------------------|
| tartare | 21% |
| sushi | 16% |
| soufflé | 12% |
| *-- sampling threshold --* | |
| ceviche | 7% |
| pizza | 0.3% |

*(Note: Fake data/example for illustration purposes only!)*

A sufficiently advanced model recognizes that Janice is a distinct person whose preferences stand in opposition to the speaker's -- and the entire prediction shifts accordingly. Nothing about the model changed; only the words it was given, and how it then leverages that important provided context to shift how it thinks the rest of the words should look.

This single move is the key: nearly everything that has happened in AI over the past year is, one way or another, just a version of leveraging this "short term memory" in increasingly creative and robust ways to get better outputs from LLMs for specific tasks. If we give it domain expertise in the context window, if we give it core data documentation info, if we give it data analysis API references, we start to get less noise and more quality, grounded output. To be really clear, though: it is still a probabilistic engine underneath, not a truth-based one, and so will always be at risk of getting it wrong. No amount of finagling with short-term memory can fully guarantee success.

### Context Windows and Context Rot

While all of that is really valuable and important, different models can only "digest" a certain amount of context before predicting the next word. That capacity is known as the model's **context window**. (Capacity is technically measured in tokens -- word fragments, with one token roughly 3/4 of a word -- but thinking in words is close enough.) For perspective: GPT-3 could only really "read" about 1,500 words -- any more than that was ignored or would break it. Claude Opus 4.6 handles roughly 150,000 words by default, with context windows of ~750,000 words in beta at time of writing (mid-2026). (DAAF's setup enables that larger ~1-million-token window by default, as noted in the [Installation Guide](01_installation_and_quickstart.md).) Expanding this capacity is one major frontier of model advancement, because the more context a model can hold, the more expertise and framing it can use for the task at hand.

But more context isn't automatically better, because **not all context is treated equally**: models weigh different parts of their context in complex, sometimes unpredictable ways. Fill the window with scattered, conflicting, or poorly structured material, and the model becomes confused, erratic, and forgetful. This failure mode is called **context rot**, and it needs to be avoided at all costs.

One subtlety that catches many people: in a chat, everything accumulates. Your first message and the model's response become part of the context that shapes its next response, and so on. Ask for help revising a syllabus, then drafting a letter to your mom, then picking a TV show, and by the third request the model is working from a weird middle-ground synthesis of all three. The generalizable advice: **have focused conversations. One task per conversation; when you switch gears, start fresh.**

### From Prompt Engineering to Context Engineering

The craft of deciding exactly how to talk to an LLM and ask it to do what you want in clear, structured ways as you chat with it is known colloquially as **"prompt engineering."** It's more of an art than a science in most circumstances -- people are largely making things up as they go and seeing what works, which means new expertise is forming in really informal communities like Reddit and X.

The most recent wave of model advancement goes a step further. Models can now read many documents you provide to it directly, and moreover interpret what you're asking for and assemble their own context dynamically: reading files they judge relevant to your request beyond what you've suggested, searching the web for current information, even delegating side-conversations to separate AI assistants whose findings flow back into the main conversation. Designing the systems, instructions, and processes that help an LLM intelligently manage and piece together its own short-term memory is called **context engineering**. It's a step beyond prompt engineering (which is about crafting individual prompts well) into something more architectural: how do you set up an entire system so the right information gets loaded at the right time, every time?

To make this concrete, here's what's actually sitting in the context window when a modern assistant responds to you:

1. **System prompt** -- provided by the model provider
2. **Custom instructions** -- provided by you, or a framework like DAAF
3. **Skills & reference files** -- loaded dynamically, as needed
4. **The conversation so far** -- accumulates turn by turn
5. **Your message** -- provided by you
6. ...and then **the model's response** -- predicted from everything above

Your message is one slice of a carefully assembled stack. Change anything above it -- the instructions, the loaded reference files, the conversation history -- and you change the response, often fundamentally.

> **Key takeaway:** Every advance you're watching in AI right now -- agents, skills, MCP servers, orchestration frameworks -- is just a different way of doing the same thing: curating what sits in the model's short-term memory, in increasingly sophisticated and automated ways, before it responds. That's really all they're doing. Learning to manage that context thoughtfully and deliberately is the highest-leverage AI skill you can build right now, regardless of what you're using AI for.

No amount of clever context engineering changes the underlying mechanic. These tools can never guarantee correct output -- they can only improve the odds of useful output. And knowing whether output is actually good requires a human expert in the loop who can review, catch, and correct it. This is why DAAF treats you as the principal investigator -- the one in the driver's seat, never a passenger: it is designed to augment your hard-earned expertise and skills rather than replace them.

---

## Three Dimensions of AI Capability

One useful way to think about where AI is right now -- and why people seem to disagree so strongly about how capable it is -- is to think about AI capability as having three interdependent dimensions:

1. **The Mind** -- the base model's raw intelligence and reasoning ability. This is what Anthropic, Google, and OpenAI are competing on with each new model release, and it's the dimension that gets the most attention when people talk about "AI progress."
2. **The Body** -- the orchestration frameworks and tooling that let the model actually *do things*: read files, run code, search the web, delegate tasks to other models. Claude Code is the "body" that lets Claude's "mind" interact with your computer. DAAF adds a much more structured and capable body on top of that.
3. **The Instructions** -- your skill in communicating what you want, plus whatever pre-built instructions the system provides. This covers everything from how you phrase a question to how an entire orchestration system like DAAF structures its instructions behind the scenes.

<img width="1253" height="419" alt="2026-03-03 AI Progress Diagram" src="https://github.com/user-attachments/assets/12c0acd5-313a-451c-ab13-851923555db2" />

Each dimension is necessary but insufficient on its own. A brilliant model with no tools can only chat. Powerful tools connected to a weak model will produce sophisticated-looking garbage. A strong model with great tools but vague instructions will go confidently in the wrong direction. The real capability of any AI system is a product of all three working together -- which is why blanket statements about "what AI can and can't do" are so often wrong. It depends enormously on the configuration.

Notice that the second and third dimensions are exactly what we just covered: the Body is tooling that lets a model act on the world and curate its own context, and the Instructions are context engineering made concrete. That's what DAAF is, at its core -- a **context engineering framework designed specifically for research workflows**. Everything in DAAF -- the skills, the agents, the orchestrator, the progressive loading of reference files -- is fundamentally an answer to the question: "What context does Claude need right now to do this specific research task well?" The [DAAF Field Guide](https://daafguide.substack.com/p/ai-progress-mental-model) has more detail on these concepts if you'd like to explore them further.

This framework also explains why people have such wildly different experiences with AI. Someone chatting casually with a basic web interface is experiencing one narrow slice of what's possible. Someone using Claude Code with DAAF and specific, well-crafted prompts is operating in a genuinely different capability regime -- not because the underlying model is different, but because the other two dimensions are dramatically more developed. The information gradient here is steep: a lot of people are still having the "AI is dumb, it can't count the Rs in strawberry" experience, while people who have invested in tooling and instruction quality are seeing capabilities that are invisible to casual users, and vice versa. This is a significant part of why the discourse around AI can feel so polarized -- people are often talking past each other because they're working with very different combinations of these three dimensions.

---

## From Intuition to Design: The Three Challenges

With that shared understanding in place, the design problem comes into focus. If we want an autocomplete engine -- however fancy the hat -- to support real research, there are three big challenges that anyone building (or evaluating) such a system will need to grapple with in some way, shape, or form:

1. **Teaching it to think like a researcher.** If we want that short-term memory filled with really useful material, what does it actually contain? It's worth pausing on the underlying question: what are the core scientific principles we hope and expect human researchers to be trained to protect and embody -- and what would those look like written down as instructions and reference files? It's not a perfect one-to-one translation, but it tells us what we're trying to preserve.
2. **Context engineering across the entire research workflow.** Research isn't one task; it's dozens of very different ones. What a careful researcher needs to know while profiling an unfamiliar dataset is completely different from what they need while specifying a regression, or interpreting complicated, conflicting results. If the research process were easy to teach, it wouldn't take a PhD to learn it -- but it does, because it's really hard. Dynamically adapting what context an AI receives at each stage is a huge engineering challenge.
3. **Proactively mitigating harms, costs, and risks.** There's the big stuff -- deleted data, leaked credentials, a misdirected email. And then there's the small stuff that matters most for research: a coding error that seems right but isn't, an interpretation that seems right but isn't, a statistical method that seems right but isn't. What permissioning, oversight, and review processes let us work confidently with a collaborator we know will sometimes be wrong?

Notice that these questions sound less like configuring software and more like teaching a new colleague and setting up a research lab. Those are exactly the design considerations behind everything that follows.

The rest of this guide is, in effect, DAAF's answer sheet. The skills and agent protocols are the answer to teaching it to think like a researcher. The engagement modes and orchestrator workflow are the answer to context engineering across the entire research process. And the dual-layer validation system is the answer to proactively mitigating harms, costs, and risks.

---

## The Mental Model: Orchestrator, Agents, Skills

Okay, this is the section where I want to give you genuine intuition for how this all works under the hood. You don't *need* to understand the architecture to use DAAF -- you can absolutely just type a research question and let it run. But if you want to understand *why* DAAF does what it does, *why* it pauses when it pauses, and *why* the output is structured the way it is, this section will hopefully make all of that click.

Thoughtfully shaping context is how we move Claude from what I lovingly describe as an over-eager recent MBA graduate -- terrible memory, very quick to please you -- into something much closer to a careful research colleague. Even after all that shaping, they're still an over-eager MBA grad at heart, so you'll still want to review their output before it goes out into the world. So I'm going to use an analogy that I think captures DAAF's architecture well: **DAAF is intended to mirror the workflows of a well-run research lab** with you as the lead researcher -- the PI, in lab terms.

### The Orchestrator: Your Lab Director

When you type a message to DAAF, you're talking to the **orchestrator**, whose core orchestration behavior is defined by the [`daaf-orchestrator` skill](../.claude/skills/daaf-orchestrator/SKILL.md), while universal execution rules come from [`CLAUDE.md`](../CLAUDE.md). Think of the orchestrator as a lab director -- the person who takes your research question, figures out what needs to be done, decides who on the team should do each piece, coordinates the whole effort, and reports back to you at key milestones.

The orchestrator should NOT be doing the hands-on work itself, because its primary value-add and contribution is coordination and workflow management. It doesn't write analysis scripts, it doesn't clean data, it doesn't run regressions. What it does is:

- **Classify your request** into an engagement mode (Full Pipeline, Data Discovery, etc.)
- **Delegate tasks** in proper sequence to specialized agents, itself providing them with the right context and instructions they need to do their jobs well
- **Enforce quality gates** -- certain milestones that MUST be passed before work continues and the work product changes hands from one agent to another
- **Report progress** to you and pause for your approval at key junctures to ensure you, the PI, approve of the direction of the work. It will also enforce work revisions as needed if you request it
- **Keep the big picture in mind** -- tracking what's been done, what's next, and what decisions have been made, to ensure it's addressing the core intentions/vision of the PI

The orchestrator is the most important part of DAAF, because it needs to simultaneously understand the whole workflow process and the broad context of the work in mind, while also being technical enough and specific enough to give precise, targeted instructions and context to every other LLM assistant involved in the process.

### Specialized Agents: Your Research Team

The "team members" in this lab are **agents** -- versions of Claude provided a clear behavioral protocol and persona defining exactly how they should think and operate. You can even see the exact context instructions provided to each in [the agents folder](../.claude/agents/). Agents are not knowledge repositories; they're *behavioral definitions*. An agent answers the question: "How should I behave when I'm doing this specific type of work?"

Here's a few examples of the team members with the links to each of their actual instruction files if you want to dig in more:

| Agent | Role in the Lab Analogy | What They Actually Do | 
|-------|------------------------|----------------------|
| [**research-executor**](../.claude/agents/research-executor.md) | Technician/Analyst | Executes one data task at a time (fetch, clean, transform, analyze) with meticulous pre/post validation |
| [**code-reviewer**](../.claude/agents/code-reviewer.md) | Senior Technician/Analyst | Reviews every single script the research-executor produces, looking for bugs, methodology errors, and data quality issues |
| [**source-researcher**](../.claude/agents/source-researcher.md) | Research Assistant | Deep-dives into a specific data source's documentation, collection protocols, caveats, and gotchas for shared team awareness |
| [**data-planner**](../.claude/agents/data-planner.md) | Research Design Lead | Synthesizes all the preliminary findings into a detailed, executable research plan |

The point here is that we want to provide very different context to Claude when faced with different tasks. Trying to get Claude to do everything equally well is impossible given fixed context window limitations, and trying to do so will ultimately confuse it and cause the dreaded **context rot** we covered earlier. This means that we need to split responsibilities across "versions" of Claude provided very different instructions and behavioral protocols to get it to perform these tasks well in tandem, each working with a lean, focused context of its own.

> **Quick definitional note:** An **Agent** is the general phrase we use to describe any tailored/pre-specified set of behavioral protocols for an LLM assistant. Each of the above team members in this analogy are Agent definitions. As a user, you can ask Claude directly to take on an agent persona and begin working. However, with DAAF's default workflows, the orchestrator actually calls up and tasks each agent above itself, so you never have to; agents become **subagents** when they are called by another assistant in this way, instead of directly by the user.

Ultimately, the orchestrator's job is to know which agent/team member to call up at any one time, and to also know very thoughtfully what it needs to tell that subagent in order for the subagent to do its job effectively with necessary context and guidance. You can see how the orchestrator is trained to talk with these agents in [the agents README](../.claude/agents/README.md) and [the orchestrator's full pipeline reference](../.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md). Subagent orchestration is an extremely new and active area of development in the broader field of AI at-large right now, which is part of why a system as complex as DAAF has only recently become possible.

### Skills: Your Team's Reference Library

If agents define *behavior* ("how should I work?"), then **skills** define *knowledge* ("what do I need to know?"). Skills are basically structured knowledge documents that agents load into their own context on demand. You can think of them as specialized reference manuals that your research team pulls off the shelf when they need domain-specific information or how-to's for a niche task or issue. These are nice because they are easily transferable across agents, and so work well for implementing knowledge/context that several agents are likely to need access to for their work.

DAAF's skills are currently organized into a few categories:

**Data source skills** -- one for each major education data source:
- What endpoints exist and what they contain
- What variables mean and how they're coded
- What caveats and limitations to watch for
- What suppression rules apply (e.g., cells with fewer than a certain number of students are suppressed for privacy)
- More historical/contextual information about the source dataset and its collection, nuances, etc.
- `education-data-explorer` and `education-data-query` for finding and fetching data
- `education-data-context` for interpreting data caveats and coded values

**Technical skills** -- how to use certain toolsets:
- `data-scientist` for general methodology, mindset/philosophy, and rigor principles
- `polars` for data manipulation in Python (similar to tidyverse or pandas)
- `tidyverse` for data manipulation in R (dplyr, tidyr, readr, purrr, and more)
- `plotnine` for static, publication-quality plots in Python (ggplot2 syntax)
- `ggplot2` for static, publication-quality plots in R
- `plotly` for interactive visualizations in Python
- `plotly-r` for interactive visualizations in R
- `marimo` for reactive Python notebooks
- `quarto` for reproducible R notebooks

**Meta skills** -- for extending DAAF itself:
- `skill-authoring` for creating and integrating new skills in a unified format and with best practices
- `agent-authoring` for creating and integrating new agents in a unified format, and with best practices 

**The key insight:** In DAAF, skills are generally intended to be loaded *by agents*, not by the orchestrator. When the orchestrator delegates a task to the research-executor, it tells the agent: "Load the `education-data-source-scorecard` skill for this task." The agent pulls up the relevant reference material, uses it to guide its work, and then returns its findings to the orchestrator. This keeps the orchestrator's context lean (it doesn't need to hold the full contents of every skill in memory) and ensures each agent gets exactly the knowledge it needs for its specific task.

<img width="2398" height="1053" alt="orchestrator_diagram" src="https://github.com/user-attachments/assets/d142b457-3459-498b-b718-4b0cb7123d29" />

> **Key takeaway:** DAAF works like a research lab. You give direction to a lab manager (the orchestrator), who delegates work to specialists (agents) who consult reference materials (skills).

Four things to keep in mind as you use DAAF:

1. In addition to the context engineering DAAF orchestrates behind the scenes, **what you ask Claude to do and how you ask it to do it** is an immensely important element of getting better quality output from DAAF/Claude. So a lot of what we'll talk about here (and in [**03. Best Practices**](03_best_practices.md)) is how to do this thoughtfully and well to maximize your chances of getting something useful from DAAF.
2. The system is **designed to intelligently select and inject the right context to Claude before your query/question/chat**, based on what you provide in your query/question/chat. But this is **NOT** foolproof, and simply cannot account for every possibility. Feel free to go off the beaten path at will, but just be aware that it's going to necessarily be less supported and structured from there; you may ultimately find it's not working very well for what you want, because I wasn't able to design for that style of work. Trying to write your query in a different way can help, or you can help us improve DAAF by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) and telling us about it!
3. Because thoughtfully shaping the context is our way of shaping Claude's thinking, DAAF really only works with the cutting-edge models -- Opus 4.6 as of mid-2026 -- and it pushes them to their limit to take advantage of their full context windows where possible. **This is why it is SO expensive to use at this time**; settling for less, we sacrifice a lot of expertise and reliability and rigor. It's a careful balancing act of optimization that no one really has fully figured out!
4. While DAAF's reference files, skills, and workflow instructions are all carefully designed to be loaded at specific moments, Claude may occasionally fail to load them, skip a step, or deviate from its instructions in subtle ways. When this happens, you get an agent working without the specialized knowledge it was supposed to have, which means it falls back on its general training -- its fuzzy long-term memory -- and that's when hallucinations, fabricated variable names, and plausible-sounding-but-wrong details creep in. This is why **Verbose output** in Claude Code's `/config` settings is particularly useful: it lets you see what DAAF's agents are actually thinking behind the scenes, including what motivates which files they're reading and which skills they're loading (or what shortcuts they're deciding on, if they are).

---

## The Nine Engagement Modes

DAAF first classifies every request you make into one of nine **engagement modes**. This is how we properly context-engineer Claude, because each mode triggers a fundamentally different workflow, different outputs, and different expectations for what input you'll need to provide to steer it well. Understanding these modes is the single most useful thing you can do to work with DAAF effectively, because it helps you frame your questions in the way most likely to get you what you actually want, and better understand what's going on behind the scenes.

Before doing anything else, DAAF will tell you which mode it's classifying your request into, explain why, and ask you to confirm. This is intentional. You should always have the chance to say "actually, I just wanted a quick lookup" or "actually, let's go deeper on this." Here's a quick reference of all nine:

| Mode | When to Use | What You Get |
|------|-------------|--------------|
| Data Lookup | Quick variable/dataset question | Direct answer with supporting context |
| Data Discovery | Scoping what data exists | Feasibility assessment, available sources |
| Ad Hoc Collaboration | Flexible working session | Thought partner for code, debugging, planning |
| Full Pipeline | Complete research analysis | Plan, scripts, notebook, report, all artifacts |
| Revision and Extension | Modify an existing analysis | New versioned artifacts, full QA |
| Data Onboarding | Profile a new dataset | Reusable data source skill |
| Reproducibility Verification | Verify a completed analysis | Reproduction Report with verdict |
| Framework Development | Modify DAAF itself | New/updated skills, agents, modes |
| User Support | Questions about DAAF/tools | Conversational help, no formal outputs |

And here's what each of them do in more detail, and how the workflow works so you know when and why you'd use each:

### Data Lookup Mode

**Trigger words:** "what are the values for," "how is X defined," "lookup," "what does this variable mean," "explain this table..."

**What it is:** A quick, focused lookup about available data tables and variables. You have a specific question about a data source, variable, coded value, or definition, and you want a direct answer without any exploration overhead. DAAF loads a single relevant data knowledge source skill and gives you what you need quickly. You can think of this like a data documentation oracle -- saving you some time on determining what data are available, limitations, year ranges, etc.

**What you get:**
- A direct, specific answer to your question
- Supporting context where relevant (e.g., "this variable uses coded values where 1=Regular school, 2=Special education, 3=Vocational...")
- Pointers to relevant documentation if you want to dig deeper

**Expected time investment:** Seconds. One question, one answer.

**When to use it:** When you already know what you're looking for and just need the specific detail. "What does `free_lunch` mean in the CCD data?" "What years are available for CRDC?" "What's the difference between `enrollment` and `fall_enrollment` in IPEDS?"

**When NOT to use it:** When your question is actually broader than you realize. If you find yourself asking five Data Lookup questions in a row, you probably want Data Discovery mode instead (described next). DAAF will suggest this if it notices the pattern.

### Data Discovery Mode

**Trigger words:** "what data exists," "is it possible," "feasibility," "what's available," "can DAAF do," "explore", "can you tell me more about variables related to..."

**What it is:** A focused investigation into what data is available, whether an analysis is feasible, and what you'd be working with if you decided to go deeper. Think of it as scoping and reconnaissance -- DAAF explores the landscape and reports back to you with what it found, but isn't running any sort of data analysis. Think of this like a scoping partner, above and beyond a basic documentation look-up.

**What you get:**
- A findings summary describing available data sources, variables, year ranges, and geographic coverage
- Key caveats and limitations for each relevant data source
- A feasibility assessment -- can the question be addressed with available data?
- If the answer is "yes, this looks promising," DAAF will offer to escalate to Full Pipeline mode

**Expected time investment:** A few minutes of conversation, usually just one or two exchanges. It might launch some "subagents" to do some digging in the background for a few minutes, too.

**When to use it:** When you're not sure what data exists for a topic, when you want to know if a question is answerable before committing to a full analysis, or when you're brainstorming research directions and want to see what's possible. This is genuinely a great starting point for new users -- ask DAAF what it can do before asking it to do it.

**When NOT to use it:** When you already know what general data exists and you're ready to analyze it with a specific research question. In that case, jump straight to Full Pipeline.

**Escalation:** If Data Discovery turns up promising data, DAAF will suggest: "Based on these findings, would you like me to proceed with a Full Pipeline analysis?" You can say yes, refine the question, or say no and walk away with just the findings.

### Ad Hoc Collaboration Mode

**Trigger words:** "help me with," "review this," "debug this," "how do I," "advise on," "think through this with me," "what's the best approach for..."

**What it is:** A flexible, multi-turn working session where you bring whatever you're working on and DAAF acts as a thought partner. This is the mode for skilled researchers who want rigorous support without committing to a formal pipeline. You might ask DAAF to review your code, help you debug a script, brainstorm an analytic approach, explain how to use a particular Python package, investigate a data source, or write a one-off analysis script. The conversation flows naturally -- you change topics, ask follow-ups, and go wherever the work takes you.

**What you get:**
- A lightweight workspace folder for anything produced during the session (scripts, data, figures)
- Access to all of DAAF's specialized capabilities -- code execution, debugging, data source research, code review, analysis planning -- on demand, as you need them
- Rigorous, methodology-aware advice grounded in the same domain expertise that powers the full pipeline

**Expected time investment:** As long as you need. There are no mandatory checkpoints or gates -- the session ends when you're done. If the session produces artifacts, DAAF will summarize what's in the workspace at the end.

**When to use it:** When you want a capable research partner for whatever you're working on right now. Some examples: "Can you review this script I wrote for cleaning CCD data?" "I'm getting a weird join error -- help me figure out what's going on." "What's the best way to handle suppressed data in a trend analysis?" "How do I use plotnine to create faceted bar charts?" "How do I use ggplot2 to create faceted bar charts with custom themes?" "Help me think through the right approach for a school-level poverty analysis."

**When NOT to use it:** When you know you want a complete, formal analysis with a Plan, Notebook, and Report -- that's Full Pipeline mode. When you just need a quick variable definition -- that's Data Lookup. Ad Hoc Collaboration is for the messy, real-world middle ground where you're actively working on something and want a knowledgeable partner.

**Escalation:** If the conversation naturally evolves toward a full analysis, DAAF will suggest: "This is shaping up to be a full analysis -- want me to formalize it into a Full Pipeline?" You can say yes, or keep working ad hoc. The workspace artifacts carry forward either way.

### Full Pipeline Mode

**Trigger words:** "analyze," "research," "create," "generate," "what's the relationship between..."

**What it is:** This is where you and DAAF collaborate on a complete analytic workflow across 5 phases: exploring available data, creating a detailed research plan, fetching and cleaning data, running analyses and creating visualizations, and delivering a comprehensive report with all supporting artifacts. This is what DAAF was fundamentally built to do as its main use-case (not to say the other modes aren't also very useful!).

**What you get:**
- A detailed research plan documenting every methodological decision
- All raw and processed data files (parquet format)
- A complete set of versioned, validated Python or R scripts covering every step of the analysis
- Statistical analysis results and high-quality data visualizations
- A compiled marimo (Python) or Quarto (R) notebook walking you through every script and its execution logs
- A stakeholder report synthesizing key findings, methodology, and limitations
- A lessons-learned document with data and process insights

**Expected time investment:** About 20-30 minutes of active engagement time spread across four "check-in" points where DAAF pauses for your review and approval, a few hours of DAAF working independently in the background, and then whatever time you (rightfully, importantly) dedicate to reviewing the final outputs. And, of course, whatever API fees you incur along the way. Full duration will depend heavily on how complex your query is: primarily how many scripts it needs to write, rewrite, and QA. Plan accordingly!

**When to use it:** When you have a genuine research question you want to explore with data. It can be as simple as "How has enrollment in rural schools changed over the past decade?" or as complex as "What's the relationship between school-level poverty, access to advanced coursework, and disciplinary disparities, controlling for school size and urbanicity?" DAAF will scope accordingly.

**When NOT to use it:** When you just need a quick answer, a variable definition, or want to know if certain data even exists. That's what the other modes are for -- and using Full Pipeline mode for a simple question is like driving a semi-truck to the corner store.

### Revision and Extension Mode

**Trigger words:** "fix," "update," "change," "modify the analysis," "revise," "redo," "can you adjust," "extend"

**What it is:** You have an existing analysis that needs changes or extension, and you want DAAF's help to improve it. Maybe you want to rethink a measure, add a new variable, change the year range, run a different statistical test, or fix something that didn't look right. First, point DAAF to the name of the project folder. Then, DAAF locates your existing project, reads the Plan, and creates a *new version* of the relevant artifacts -- it never modifies the originals.

**What you get:**
- A new version of the Plan document incorporating your changes
- Updated scripts, data, and outputs as needed
- A full Final Review even for minor fixes (no shortcuts on quality)
- All prior versions preserved in the same project folder

**Expected time investment:** Depends on the scope of the revision. Changing a year range might take 15 minutes; fundamentally rethinking the methodology could be nearly as long as a new analysis (and you may seriously want to consider going that route instead with clearer and more directed prompts/research questions, depending!).

**When to use it:** After you've received a completed analysis and want to adjust something. Reference your project by keywords or date -- e.g., "Can you update the Texas poverty analysis to include 2023 data?" or "In the 2026-01-15 enrollment study, can we use a different measure of school size?"

**How the version system works:** All versions live in the same project folder. Prior versions are **never** modified or overwritten -- that's a non-negotiable rule. The versioning uses date suffixes: the original analysis might be `2026-01-24`, revision 1 becomes `2026-01-24a`, revision 2 becomes `2026-01-24b`, and so on. This means you always have a full audit trail of how the analysis evolved.

**When NOT to use it:** When your existing analysis is fundamentally flawed or you want to ask a substantially different research question. At that point, starting a new Full Pipeline analysis with better-targeted prompts will produce cleaner results than trying to revise the original into something it wasn't designed to answer.

### Data Onboarding

**When to use:** You have a raw data file (CSV, Parquet, Excel, etc.) that you want to profile and add as a reusable data source for future analyses.

**What happens:** DAAF runs a thorough profiling protocol (up to 11 scripts, depending on data characteristics) in 3 top-level phases (Setup, Profiling, Skill Creation). The Profiling phase contains 4 sub-phases: Structural Discovery, Statistical Deep Dive, Relational Analysis, and Interpretation & Reconciliation. You review the findings and confirm the interpretations before DAAF creates a standalone data source skill. After that review, DAAF offers (optionally — you can skip it in one word) to research the source online first, so the skill's methodology, coverage, and limitations sections are grounded in the source's documentation and the research literature rather than inference. The entire process is tracked in a reproducible research project folder.

**What you get:** A standalone data source skill (`.claude/skills/`) that future analyses can reference, plus a research project folder with all profiling scripts, QA reviews, and session state.

**A fork in the road -- the sensitivity gate:** Right at the start of onboarding, DAAF asks you directly whether your data is sensitive -- PII, proprietary, regulated (FERPA/HIPAA), locked in a secure enclave, or simply something that can't leave your environment. This is the "sensitivity gate." If you confirm the data is safe to bring in, onboarding proceeds normally (the data is copied into the container and profiled there). But if you *can't* confirm that -- if the data genuinely shouldn't enter the container -- DAAF takes a different path entirely: the **synthetic-data protocol**. Instead of importing your data, DAAF hands you a disclosure-controlled profiling script that you run yourself, wherever the data lives. Only a summary profile report crosses the boundary; DAAF then builds a synthetic stand-in dataset and a data source skill from that report alone, so you can develop and debug your whole analysis against realistically-shaped fake data. The real data never enters the container. When your code is finished and vetted, you run it against the real data yourself, in its own secure environment, to get the actual results. It's a way to get almost all of DAAF's help without ever exposing the sensitive data itself. (For the full picture, see the FAQ entry [Can I use DAAF with data that can't leave my secure environment?](07_faq_technical.md#q-can-i-use-daaf-with-data-that-cant-leave-my-secure-environment).)

**Checkpoints:** 2 -- one after project setup (to confirm the profiling plan), and one after profiling completes (to review and confirm/modify the preliminary interpretations before they become part of the skill).

**Example prompts:**
- "I have a CSV of county-level election returns I'd like to profile and add as a data source"
- "Profile this parquet file and create a skill I can use in future analyses"
- "I want to ingest a new dataset about hospital readmission rates"

### Reproducibility Verification Mode

**Trigger words:** "verify," "reproduce," "reproduction," "does this replicate," "check reproducibility," "verify this analysis..."

**What it is:** You have an existing completed analysis (from a Full Pipeline run or otherwise) and you want to mechanically verify that it reproduces from its marimo or Quarto notebook. DAAF decompiles the notebook back into standalone scripts, re-executes each one, compares the new outputs against the originals, and cross-references the Report's claims against the actual analytic results. The goal is to provide an independent, systematic assessment of whether the analysis holds up end-to-end.

**What you get:**
- A Reproduction Report documenting what matched, what diverged, and any methodological concerns discovered during the process
- An overall assessment of **FULLY REPRODUCED** (all outputs match within tolerance, report claims supported), **PARTIALLY REPRODUCED** (some outputs diverge or some claims unsupported, but core findings hold), or **NOT REPRODUCED** (significant divergences or unsupported claims that undermine the analysis)
- Detailed comparison logs showing exactly where and how outputs differed, if at all

**Two key user decisions:**
- **Whether to re-fetch data** (default: yes). Re-fetching tests whether the analysis reproduces against the current state of the data source. Skipping re-fetch tests whether the analysis reproduces from the already-downloaded raw data files.
- **Methodological review depth** (default: light). A light review focuses on mechanical reproduction -- do the scripts run and produce matching outputs? A deep review additionally scrutinizes methodological choices, statistical assumptions, and interpretation quality.

**Expected time investment:** Depends on the complexity of the original analysis. A straightforward single-source analysis might take 15-30 minutes; a multi-source analysis with extensive transformations could take longer. You'll review the Reproduction Report at the end.

**When to use it:** After completing a Full Pipeline analysis and wanting to verify it reproduces before sharing or publishing. When reviewing someone else's DAAF analysis and wanting an independent verification. For periodic verification of important findings to ensure they still hold against updated data sources.

**When NOT to use it:** When you already know the analysis needs changes -- use Revision and Extension mode instead. When the analysis was never completed or has no notebook -- there's nothing to reproduce from.

### Framework Development

**Trigger words:** "create a skill", "add an agent", "add a mode", "modify DAAF", "update the template", "extend the framework"

**What it is:** A structured collaboration mode for modifying DAAF itself — its skills, agents, modes, reference files, templates, and configuration. The orchestrator scopes the current state of whatever you want to change, presents findings, then authors or modifies framework artifacts following canonical templates with a full integration checklist.

**What you get:** Modified or new framework components placed directly in the DAAF codebase, with a multi-angle review pass ensuring cross-file consistency.

**When to use it:** When you want to add a new data source skill, create a new agent, add a new engagement mode, update templates or reference documents, incorporate learnings from completed analyses back into the framework, or make any other structural change to the DAAF framework.

**When NOT to use it:** When you want to onboard a dataset by profiling it (use Data Onboarding), when you want to run an analysis (use Full Pipeline), or when you want general help (use Ad Hoc Collaboration).

**Two checkpoints:**
1. After scoping — confirm the approach before any modifications begin
2. After review — approve the final state of all changes

**Escalation:** Can escalate to Data Onboarding (if you need to profile data, not just create a skill template), Full Pipeline (to test a new skill with actual analysis), or Ad Hoc Collaboration (if you need general help rather than framework changes).

### User Support Mode

**Trigger words:** "what is DAAF," "how does this work," "help me understand," "something's not working," "what can you do," "explain this to me," "Docker," "Git," "Claude Code help"

**What it is:** A lightweight, conversational mode for questions about DAAF itself and the tools it runs on -- Docker, Git, and Claude Code. If you want to know how DAAF works, what it can do, how to troubleshoot a Docker or setup problem, how to use Git with your projects, or how to get the most out of the framework -- this is where you start. The orchestrator loads the core user documentation and responds directly, and can look up official documentation for Docker, Git, and Claude Code online when needed. No subagents are dispatched, no workspace is created, and no formal deliverables are produced. This is the only mode where DAAF itself (and its technology stack) is the subject, rather than your data or analysis.

**What you get:**
- Direct, educational answers to any question about DAAF -- its modes, agents, skills, architecture, design philosophy, troubleshooting, and best practices
- Help with the underlying tools: Docker container management, Git version control, Claude Code configuration and features
- Answers grounded in official documentation when needed (Docker docs, Git docs, Claude Code docs)
- File paths to relevant documentation if you want to read further
- Gentle routing to the right mode when your questions naturally evolve into wanting to *do* something, not just learn about something

**Expected time investment:** As long as you need. There are no checkpoints, no gates, no deliverables. Just a conversation.

**When to use it:** When you're new and want to understand what DAAF is before jumping in. When you want to know which mode fits your needs. When you're troubleshooting a Docker, Git, or setup issue. When you're curious about how agents, skills, or the pipeline work under the hood. When you want tips on writing better prompts or reviewing output more effectively. When you have questions about Claude Code features or configuration.

**When NOT to use it:** When you already know what you want to do. If you have a specific data question, a research question, or a hands-on task -- jump straight into the relevant mode (Data Lookup, Full Pipeline, Ad Hoc Collaboration, etc.). User Support is for *understanding* DAAF and its tools, not for *using* it to work with data.

**Escalation:** When your questions naturally evolve into an action ("Okay, I think I'm ready to try running an analysis"), DAAF will suggest the appropriate mode and wait for your confirmation. It routes, it doesn't gatekeep -- you never need to "graduate" from User Support before using other modes.

### Switching Between Modes

DAAF supports clean transitions between modes when your work naturally evolves. You don't need to memorize every possible transition -- DAAF will suggest the right mode at natural breakpoints and wait for your confirmation. It should never silently switch modes on you.

Here are the most common transitions you'll encounter:

| From | To | When it happens |
|------|----|-----------------|
| Data Discovery | Full Pipeline | Your exploration revealed a feasible, interesting analysis |
| Full Pipeline | Revision and Extension | You completed an analysis and want to adjust or extend it |
| Data Onboarding | Full Pipeline | You profiled a dataset and now want to analyze it |
| Ad Hoc Collaboration | Full Pipeline | Your working session evolved into something worth formalizing |
| Full Pipeline | Reproducibility Verification | You want to verify a completed analysis reproduces |
| Any mode | User Support | You have questions about how DAAF or its tools work |

Beyond these common paths, DAAF supports transitions between any pair of modes where the shift makes sense -- for example, a Data Lookup that reveals a broader question might escalate to Data Discovery, or a completed analysis might surface framework improvements worth addressing in Framework Development mode. The full transition matrix is handled internally; the important thing to know is that DAAF will always propose a transition explicitly and explain why before making it.

> **Key takeaway:** Think of these as different types of conversations, from a quick factual question to a complete multi-hour research project. You choose the scope; DAAF adapts.

---

## Easing in with Progressively More Advanced Queries

Rather than try to jump in with a complete Full Pipeline Analysis at once, I strongly recommend testing out the simpler features and engagement modes first. The whole premise of this project is that DAAF is surprisingly robust, but I think the right way to build confidence is to start small and work your way up. Here's a concrete progression I'd recommend, designed to let you assess DAAF's knowledge and capabilities at each level of complexity:

### Level 1: Quick Ask (Data Lookup Mode)

Ask Claude to explain a single dataset or variable you're already familiar with. This tests DAAF's domain knowledge against your own expertise.

```
What is the CRDC dataset and what does it contain? How often is
it collected?
```

or

```
How is free/reduced-price lunch eligibility defined in the CCD
data? What are the coded values?
```

**What you're testing:** Does DAAF know the data as well as you do? Are there gaps in its knowledge? Does it mention the right caveats? Feel free to ask follow-ups or dig into specific details -- this is a safe, low-stakes way to calibrate your trust.

### Level 2: Thorough Documentation Review (Data Discovery Mode)

Ask Claude to help you figure out what's available within a broad conceptual category of data. This tests DAAF's ability to explore multiple options, consider trade-offs, notice year overlaps or gaps, and so on.

```
I'm considering a research project looking more at college and university finances. Can you help me explore what datasets and variables are likely to be of interest for this work?
```

or

```
I know there are a couple of different ways of measuring school poverty. Can you give me a good sense of what the options are and what their relative trade-offs might be?
```

**What you're testing:** How does DAAF surface relevant information, variables, tables, and so on, when faced with broader options and less explicit direction? What issues might arise, and does it seem to recognize strengths/pitfalls of each possibility it flags appropriately?

### Level 3: Data Onboarding (Data Onboarding Mode)

If you have your own dataset that you'd like to bring into DAAF, try profiling it with Data Onboarding mode. This is a great way to expand DAAF's capabilities with your own data.

```
I have a CSV of county-level election returns I'd like to profile
and add as a data source. The file is at:
/daaf/data/county-elections/election_returns_2024.csv
```

or

```
Profile this parquet file and create a skill I can use in future
analyses: /daaf/research/my-data/hospital_readmissions.parquet
I also have a data dictionary at: /daaf/research/my-data/codebook.pdf
```

**What you're testing:** Can DAAF systematically profile a dataset you know well, detect its structure, identify coded values and quality issues, and produce a reusable skill? Do its preliminary interpretations match your domain knowledge? This is also a great way to contribute back to the community by sharing new data source skills.

### Level 4: Single Variable Analysis (Simple Full Pipeline)

Ask DAAF to analyze a single variable from a single dataset you already know well. This will kick off a Full Pipeline run, but a very simple and approachable one.

```
Can you analyze the distribution of school-level poverty rates
across all public elementary schools in California for the most
recent year available? I'm interested in basic descriptive
statistics and a histogram.
```

**What you're testing:** Can DAAF correctly fetch, clean, and describe a dataset you're already familiar with? Do the descriptive statistics match what you'd expect? Is the cleaning approach reasonable? This is where you start validating DAAF's *execution* quality, not just its knowledge.

### Level 5: Simple Correlational/Longitudinal Analysis

Ask DAAF to look at the relationship between two variables of interest, possibly over time.

```
Help me understand how average school-level poverty rates have
changed over the past decade for public high schools, broken out
by urbanicity (city, suburb, town, rural). Show me the trends
and any notable patterns.
```

**What you're testing:** Can DAAF handle multi-year data, create meaningful groupings, and produce time-series visualizations? Are the trends sensible? Does it properly handle years with data quality issues (COVID years, for instance)?

### Level 6: Multivariate Analysis

Now get more abstract and complex. Ask about relationships between multiple variables that require joining data sources and more sophisticated statistical approaches.

```
Help me better understand the relationships between college
selectivity, student academic preparedness, graduation rates,
and student socioeconomic backgrounds. What patterns emerge
when we look at these together?
```

or

```
What linkages exist between school-level resources (per-pupil
expenditure, teacher-student ratio), student socioeconomic
status, and access to advanced coursework? Can you tease apart
these relationships?
```

**What you're testing:** Can DAAF correctly join multiple data sources, handle the complexity of multi-variable analysis, and produce interpretable results? This is where DAAF's rigorous validation pipeline really earns its keep -- there are many more places for subtle errors to creep in.

**Pro tip for this level:** You can even ask DAAF what you should ask it! Try:

```
I'm trying to think of moderately complex research questions
I could use to test the DAAF system, based on the education
data available. Can you suggest a few options related to
educational equity?
```

### Level 7: Replication Exercises

The ultimate test of an analytical framework: can it reproduce results from published research? I am actively trying to assess DAAF's performance by replicating studies conducted by the [Urban Institute's Learning Curve series](https://www.urban.org/projects/learning-curve), which leverage the same Education Data Portal datasets DAAF currently has access to. Many of these studies have [open-source code available](https://github.com/UrbanInstitute/The-Learning-Curve/tree/main) for direct comparison.

You'll want to pick one where the data was solely pulled from the Education Data Portal, and then think about exactly how to rephrase and pose the research question to DAAF to reasonably target the same questions and variables if full, actual replication is your goal. Feel free to steer it as needed conceptually to align.

**What you're testing:** The gold standard -- can DAAF produce results consistent with published, expert-produced research? This is the most rigorous test possible and will surface any systematic issues in the pipeline. There is a genuine and important garden of branching pathways issue here, where different phrasing may suggest different priorities (and thus different decisions made about data specification trade-offs, etc.), but you should be able to get into the right territory. You should also be able to diagnose where and why things diverged, if they did.

If you run replication exercises, I would genuinely love to hear about your results. Please share your findings by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) -- this kind of validation is invaluable for the entire community.

### Level 8: Charting your own path

From here, you've hopefully gotten a good sense of what DAAF can and cannot do as of right now. It's got strengths, it's got limitations, and there are ways to use it that will probably be more or less useful for different people. My goal here is not to make the single, end-all-be-all best tool for everyone, but to create a unified, pretty good starting point. Use it how you see fit, and if you find ways to make it work better for you, people in the community would probably also benefit from you sharing that knowledge back with others! See [**04. Extending DAAF**](04_extending_daaf.md) and [**05. Contributing**](../CONTRIBUTING.md) for more info there.

Either way, please do keep me posted on what you learn and experience! This is a joint exploration endeavor, at the end of the day.

---

## Anatomy of a Completed Analysis

After a Full Pipeline run completes, you'll have a project folder containing everything DAAF produced.

### The Project Folder

Every analysis lives in a self-contained folder under `research/`, named with the date and a descriptive title:

```
research/2026-01-24_School_Poverty_Analysis/
├── 2026-01-24_School_Poverty_Analysis_Plan.md
├── 2026-01-24_School_Poverty_Analysis_Plan_Tasks.md
├── 2026-01-24_School_Poverty_Analysis.py       (Python: marimo notebook)
│   or 2026-01-24_School_Poverty_Analysis.qmd   (R: Quarto notebook)
├── 2026-01-24_School_Poverty_Analysis_Report.md
├── LEARNINGS.md
├── STATE.md
├── logs/                             (session transcripts, collected at completion)
├── scripts/
│   ├── stage5_fetch/
│   │   ├── 01_fetch-ccd.py           (Python: .py / R: .R)
│   │   └── 02_fetch-meps.py
│   ├── stage6_clean/
│   │   ├── 01_clean-ccd.py
│   │   └── 02_clean-meps.py
│   ├── stage7_transform/
│   │   ├── 01_join-data.py
│   │   └── 02_derive-variables.py
│   ├── stage8_analysis/
│   │   ├── 01_regression-poverty.py
│   │   └── 02_enrollment-plot.py
│   ├── cr/
│   │   ├── stage5_01_cr1.py
│   │   ├── stage5_02_cr1.py
│   │   ├── stage6_01_cr1.py
│   │   └── ...
│   └── debug/                        (if debugging was needed)
├── data/
│   ├── raw/
│   │   ├── 2026-01-24_ccd_schools.parquet
│   │   └── 2026-01-24_meps_poverty.parquet
│   └── processed/
│       ├── 2026-01-24_ccd_clean.parquet
│       └── 2026-01-24_analysis.parquet
└── output/
    ├── analysis/
    │   └── 2026-01-24_regression_results.parquet
    ├── figures/
    │   └── 2026-01-24_poverty_distribution.png
    └── preliminary_notes/
```

> **Note on execution language:** The folder structure is identical whether using Python or R. The differences are in file extensions (`.py` vs `.R` for scripts) and notebook format (`.py` marimo notebook vs `.qmd` Quarto notebook). Your execution language is set in CLAUDE.md's User Preferences section -- DAAF handles the rest automatically.

**Tip:** The easiest way to browse a completed project is with the browser-based code editor. Run `bash run_vscode.sh` (or `.\run_vscode.ps1` on Windows) from your `daaf-docker` folder, then navigate the file tree in the sidebar. You can preview Markdown reports and plans with `Shift+Ctrl+V`, read Python and R scripts with syntax highlighting, and inspect the Git history to see what changed and when. See [**03. Best Practices — Using the Browser-Based Code Editor**](03_best_practices.md#using-the-browser-based-code-editor) for more.

Let's go through each piece.

### The Plan Document (Plan.md)

**What it is:** The single most important artifact in the project. Plan.md is DAAF's strategic research specification -- it captures everything about what was done and *why*. If the scripts are the "what," Plan.md is the "why."

**What's inside:**
- **Research Question** -- your original question, verbatim, plus any clarifications
- **Research Outcomes** -- specific, measurable topics the analysis must rigorously investigate and report on (e.g., "Relationship between school poverty rates and AP course enrollment is characterized with direction, magnitude, significance, and confidence intervals"). These define what must be *examined*, not what the answer should be. Directional predictions belong in the optional Hypotheses section.
- **Data Sources** -- which datasets are being used, what endpoints, what years, and why
- **Methodology** -- the statistical approach, key decisions, and their rationale
- **Risk Register** -- what could go wrong and how to handle it
- **Key Decisions Log** -- every methodological choice made during the project, with reasoning

**How to read it:** Start with the Research Question and Research Outcomes -- do they match your intent? If any outcomes read like hypotheses (predicting a direction), flag them. Check the Key Decisions Log for anything surprising. Plan.md is meant to be comprehensive enough that someone unfamiliar with the project could understand exactly what was done and why.

**Why it matters:** Plan.md is your audit trail. If you or a colleague ever needs to understand how a finding was derived, Plan.md traces the full chain of reasoning from question to methodology to execution. It's also what makes Revision and Extension Mode possible -- DAAF reads the existing Plan.md to understand what was done before proposing changes.

A companion file, **Plan_Tasks.md**, contains the detailed machine-readable task specifications that DAAF uses internally to execute each step. It includes the exact ordered Transformation Sequence of tasks (fetch, clean, transform, analyze, visualize) with dependencies, wave assignments for parallel execution, and input/output file paths. Both files are frozen after planning completes. You can review Plan_Tasks.md if you want to audit the specific task definitions, but Plan.md is the primary document for understanding the research design.

### The Scripts Directory

**What it is:** The primary execution artifacts. I cannot stress this enough -- **the scripts are the real work product**, not the notebook. Every data fetch, every cleaning operation, every transformation, every analysis, and every visualization is captured as a standalone Python or R script in the `scripts/` directory, organized by stage. I cannot stress enough: Get a sense for how these scripts are actually written and run: **this is the secret sauce of why anything about DAAF is worth anything at all**. Without the core engine of data analysis being transparent, rigorous, and reproducible, nothing else that comes out of this process is valuable. Spend time here.

**What's inside each script:**
- Clear section headers (`# --- Config ---`, `# --- Load ---`, `# --- Transform ---`, `# --- Validate ---`, `# --- Save ---`)
- Inline audit trail comments explaining the *intent* and *reasoning* behind every operation (not just what the code does, but *why*)
- Embedded validation: `assert` and `print` statements in Python, or `stopifnot()` and `cat()` in R, showing data shape, distributions, etc.
- An **appended execution log** at the bottom of each script (added automatically after execution) showing exactly what happened: duration, exit code, stdout/stderr output, pre/post data state

**How to read scripts:** Scripts read top-to-bottom like a lab notebook -- no functions, no classes, no jumping around. Start at the top, follow the comments, and then check the execution log outputs at the bottom. The execution log is the "ground truth" for what actually happened when the script ran.

**Script versioning:** When a script fails a quality review (part of the [Dual-Layer Validation](#dual-layer-validation) system explained below) and needs to be revised:
- Original `01_task.py` keeps its failed output (it's part of the audit trail)
- Revision `01_task_a.py` contains the fixes with its own execution log
- Further revisions use `_b.py`, `_c.py`, etc.
- The notebook only includes the final successful version

**The `cr/` subdirectory:** This is where the code-reviewer's QA inspection scripts live. Each `cr` script is a diagnostic that the code-reviewer wrote and ran to verify a specific analysis script. The naming convention is `stage{N}_{step}_cr{iteration}.py` -- so `stage5_01_cr1.py` is the code-reviewer's first inspection of the first Stage 5 script. If the reviewer found something suspicious and needed to investigate further, you'll see `cr2`, `cr3`, etc.

### The Research Notebook (Marimo or Quarto)

**What it is:** A compiled walkthrough of all the validated scripts, assembled into a notebook you can view in your browser. DAAF uses **marimo** (`.py`) for Python projects and **Quarto** (`.qmd`) for R projects. In both cases, the notebook is *not* where the analysis was done -- it's a presentation layer that lets you browse the completed work.

**What's inside:**
- **Section headers** identifying which script stage is being shown
- **Code cells** containing the literal code from each script file (commented out so it doesn't re-execute)
- **Execution log accordions** showing exactly what happened when each script ran -- verbatim, not summarized
- **Data inspection cells** that load the output parquet files and display them as interactive tables (the *only* new code in the notebook)

**What you won't see:** New analysis code, interactive dashboards, filter widgets, or additional transformations. The notebook is a viewer, not an analysis tool. This is by design -- it ensures that what you see in the notebook is exactly what was executed and validated in the scripts, with nothing added or changed.

**How to view marimo notebooks (Python):** The easiest way is to run `bash view_notebooks.sh` (or `.\view_notebooks.ps1` on Windows) from your `daaf-docker` folder — this opens marimo's notebook browser at [http://localhost:2718](http://localhost:2718) where you can browse and open any notebook. Alternatively, from inside the container you can view a single notebook read-only with:
```bash
marimo run 'research/YYYY-MM-DD_Title/YYYY-MM-DD_Notebook.py' --host 0.0.0.0 --port 2718 --headless
```
You can also open the `.py` file in any text editor -- marimo notebooks are just Python.

**How to view Quarto notebooks (R):** The easiest way is to run `bash view_quarto.sh` (or `.\view_quarto.ps1` on Windows) from your `daaf-docker` folder -- run it with no argument to list every `.qmd` notebook, or pass a project folder to render and open one. It renders the notebook to a single self-contained HTML file inside the container, copies it out to a `quarto_html/` folder on your host, and opens it in your browser (the R-notebook counterpart to `view_notebooks.sh` for Python). Alternatively, from inside the container you can render by hand with `quarto render 'research/YYYY-MM-DD_Title/YYYY-MM-DD_Notebook.qmd'`, then view the resulting HTML file in the browser-based code editor. You can also open the `.qmd` file directly in any text editor -- Quarto notebooks are plain text with YAML frontmatter and code chunks.

### The Report

**What it is:** A stakeholder-facing summary report synthesizing the key findings, methodology, data, limitations, and visualizations into a readable narrative. Think of it as the "executive summary" version of the analysis -- what a colleague, policymaker, or reviewer would want to read to understand what was found and how.

**What's inside:**
- Executive summary with headline findings
- Detailed methodology section (data sources, cleaning approach, statistical methods)
- Key findings with supporting statistics and figure references
- References section (data sources, methodological references, software & tools, and reporting standards — DAAF tracks these automatically during execution, though you should verify they are accurate and complete)
- Data limitations and caveats
- Appendices with technical details

**How it differs from the notebook:** The notebook is for thorough *methodological inspection* -- browsing every line of code and verifying what happened. The report is for *communication* -- telling the story of what was found and what it means. They're complementary artifacts serving different audiences.

**How to view it:** The report is a Markdown (.md) file. The easiest way to read it with proper formatting is in the browser-based code editor — run `bash run_vscode.sh` (or `.\run_vscode.ps1` on Windows) from your computer's `daaf-docker` folder (i.e., don't run the terminal inside the container for this), navigate to the report file, then right-click and select **"Open Preview"** (or press `Shift+Ctrl+V`) to see the rendered Markdown with headers, tables, and formatting. 

### Data Files (Raw and Processed)

**`data/raw/`** -- The original data files exactly as they were fetched from the data sources. These are your "original ingredients" and are never modified after download.

**`data/processed/`** -- Cleaned and transformed versions of the data, including the final analysis dataset. These are the files that were actually used for statistical analyses and visualizations.

**Why parquet?** Every data file is saved in Apache Parquet format. Parquet is a columnar storage format that preserves data types (integers stay integers, dates stay dates), compresses efficiently, and is fast to read. CSV files lose type information (everything becomes a string), which introduces subtle bugs. Parquet prevents an entire category of data quality issues. You can open parquet files in Python (with `polars` or `pandas`), R (with `arrow`), or many other tools.

### Output: Analysis Results and Figures

**`output/analysis/`** -- Statistical analysis results saved as parquet files. Regression coefficients, summary statistics, comparison tables, etc.

**`output/figures/`** -- Data visualizations saved as PNG images. These are the same figures referenced in the report. You can open them with any image viewer.

**`output/preliminary_notes/`** -- Complete, uncompressed findings from discovery-phase specialists -- data exploration results, source-specific research, and the research synthesis. These files ensure that downstream analysis steps have access to the full detail from early research, not just summaries.

### STATE.md and LEARNINGS.md

**STATE.md** -- A session state file that tracks DAAF's progress through the analysis. It records transformation progress, checkpoint statuses, runtime decisions, and any blockers encountered. It also accumulates the QA Findings Summary (aggregated quality review results across all stages), the Final Review Log (from the end-of-pipeline verification), any Runtime Risks discovered during execution, and Citations Accumulated (a running ledger of data source, methodological, software, and reporting standard citations extracted as each script executes). If a session is interrupted (context exhaustion, network issues, etc.), STATE.md allows DAAF to resume exactly where it left off. You generally don't need to read this unless debugging a session issue.

**`logs/`** -- Session transcripts collected into the project folder at completion. When a project finishes, DAAF gathers all session transcripts that touched the project's files into this directory, making each project self-contained for audit purposes. If an analysis spanned multiple sessions, you'll find transcripts from each one here. These are copies of the global archives in `.claude/logs/sessions/` -- see the [Session Logs and Diagnostics FAQ](07_faq_technical.md#session-logs-and-diagnostics) for details on formats and storage. You can browse these logs visually using the **DAAF Log Explorer**, an interactive timeline that shows orchestrator actions, subagent dispatches, and tool calls in your browser — run `bash view_logs.sh` (or `.\view_logs.ps1` on Windows) from your `daaf-docker` folder on the host. See the [Installation Guide — Viewing Session Logs](01_installation_and_quickstart.md#viewing-session-logs-in-your-browser) for details.

**LEARNINGS.md** -- A lessons-learned document capturing insights about the data and the analysis process. This includes data idiosyncrasies discovered during the analysis, interpretation concerns, and suggested improvements to DAAF's documentation. This file is designed to be immediately actionable -- you can share it back with the community to help improve DAAF for future users.

---

## Looking at the Sample Projects

To help illustrate what DAAF does and how it works, the repository includes two sample projects in the `research/` folder. Each has its own README with a detailed walkthrough of every artifact.

### Full Pipeline Sample

The [**College Graduation Rate & Selectivity Analysis**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/) demonstrates a complete Full Pipeline analysis exploring the complicated relationship between college selectivity and graduation rates. Start with the [project README](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/README.md) for a guided tour, or jump straight to the highlights:

- [**The Report**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md) -- A stakeholder-ready research report with 8 key findings, 6 visualizations, and full AI use disclosure
- [**The Plan**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md) -- The research blueprint showing DAAF's discovery findings, methodology, and 33-task execution plan
- [**A data fetch script**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py), a [**data join script**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/01_join-core.py), a [**code QA script**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr2.py), and a [**statistical analysis script**](../research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py)

This project is presented warts and all -- some of the interpretation is arguably overblown, and some analytical choices could be questioned. That's the point: DAAF produces work that is **worth reviewing**, not work that can be trusted blindly. There's a LOT to be impressed by here, but it IS NOT PERFECT and DOES need human review. Please use DAAF accordingly!

### Reproducibility Verification Sample

The [**Reproducibility Verification of the same analysis**](../research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/) demonstrates what it looks like when DAAF independently re-runs and verifies a completed project. Start with the [project README](../research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/README.md) for a guided tour, or jump to:

- [**The Reproduction Report**](../research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/Reproduction_Report.md) -- The full verification verdict: 34 scripts re-executed, 53 quantitative claims verified, all findings supported

These sample projects together should give you a good sense of what to expect across DAAF's most comprehensive modes.

---

## Dual-Layer Validation

This is where DAAF really earns its keep -- where it most directly confronts that third challenge from earlier, and honestly where I think the biggest gap exists in most ad-hoc, LLM-assisted analysis today. Remember the core mechanic: a probabilistic engine can never guarantee correct output, only better or worse odds of it. So DAAF assumes errors *will* happen and builds two independent layers of validation that work together to catch them before they reach you.

### Layer 1: Primary Validation (CP1-CP4)

These are validation checks *embedded directly in the analysis scripts themselves*. Every script the research-executor writes includes built-in assertions and checks that run automatically:

| Checkpoint | When It Runs | What It Catches |
|------------|-------------|-----------------|
| **CP1** | After data fetch | Empty datasets, wrong data types, >90% missing values in critical fields |
| **CP2** | After data cleaning | Invalid coded values, suppression rates above 50%, impossible analysis types |
| **CP3** | After each transformation | Unexpected row loss (>90%), broken joins, surprise null values |
| **CP4** | Before final output | Missing required outputs, deviations from the plan |

If a checkpoint fails, execution stops. Period. DAAF doesn't try to power through -- it reports the failure and either attempts a fix or escalates to you.

### Layer 2: Secondary Validation (QA1-QA4b)

After every single script passes its embedded checkpoints, a *completely separate agent* -- the `code-reviewer` -- independently inspects both the code and its output data. The code-reviewer approaches each script with an adversarial mindset, specifically looking for:

| QA Checkpoint | When It Runs | What It Catches |
|---------------|-------------|-----------------|
| **QA1** | After fetch scripts | Schema problems, ID uniqueness violations, suspicious distributions |
| **QA2** | After cleaning scripts | Incorrect coded value handling, flawed filtering logic |
| **QA3** | After transformation scripts | Bad join cardinality, aggregation errors, derived column mistakes |
| **QA4a** | After analysis scripts | Invalid statistical methods, violated assumptions, unreliable results |
| **QA4b** | After visualization scripts | Misleading charts, incorrect data sources, missing labels |

**Why two layers?** Because they catch different types of errors. Primary validation catches *operational failures* -- the data is empty, the types are wrong, something clearly broke. Secondary QA catches *methodological errors* -- the code runs fine and produces output, but the methodology is wrong, the join logic is subtly off, or the interpretation doesn't match what the data actually shows. These are the insidious errors that humans regularly miss when reviewing LLM-generated code, and they're exactly the errors that matter most for research integrity.

**The critical rule:** Every script should get both layers of review. No exceptions. And the code-reviewer inspects each script *immediately* after it's executed -- not batched at the end of a stage. This matters because an error in script 1 that goes undetected will silently propagate through scripts 2, 3, and 4, compounding into a mess that's far harder to diagnose and fix.

> **What this looks like in practice:** Two real catches from the sample analysis described in [Looking at the Sample Projects](#looking-at-the-sample-projects). During data acquisition, the code-reviewer flagged that a variable named `open_public` was being interpreted as "open admissions" -- a sanity check showed Harvard and Stanford both coded as 1, because the field actually means "currently operating." The selectivity classification at the heart of the analysis would otherwise have been silently wrong. Later, during independent final verification, the data-verifier traced every key statistic in the draft report back to the raw script outputs and found a regression coefficient that had been plausibly invented rather than transcribed -- an error that changed the report's central claim -- and blocked delivery until it was corrected against the execution log.

### The Full Pipeline Flow

The orchestrator coordinates all of the specialized agents for different tasks across the pipeline. You don't need to memorize who does what -- DAAF manages the team automatically. The important thing is understanding the overall flow and where your review points are.

Here's how a typical task flows through the system during a Full Pipeline analysis:

1. **You** ask a research question
2. **The orchestrator** classifies the request as Full Pipeline and confirms with you
3. **The orchestrator** delegates data exploration to a subagent, which loads the `education-data-explorer` skill
4. **The orchestrator** delegates source deep-dives to `source-researcher` agents (one per data source), each loading the appropriate `education-data-source-*` skill
5. **The `research-synthesizer`** consolidates all findings into unified guidance
6. **The orchestrator** pauses for your review (Phase Status Update 1) ← *your checkpoint*
7. **The `data-planner`** creates a detailed Plan, validated by the **`plan-checker`**
8. **The orchestrator** pauses for your review again (Phase Status Update 2) ← *your checkpoint*
9. **A separate `research-executor`** is called up to work through each task in the Plan, one at a time, with **a separate `code-reviewer`** inspecting each script immediately after execution
10. **The orchestrator** pauses twice more for your review to provide updates and get your input on any key decisions/issues (Phase Status Updates 3 and 4) ← *your checkpoints*
11. **The `notebook-assembler`** compiles all scripts into a browsable notebook
12. **The `report-writer`** creates the stakeholder report
13. **The `data-verifier`** performs adversarial final verification on the final report, checking it closely for errors and drift from the outputs of the actual analytic scripts
14. **The orchestrator** delivers everything to you with file paths for final review.

That's the core loop. Every piece has a job. Every job has a quality check. Every quality check has consequences (stop, revise, or proceed). And you get four mandatory check-in points where DAAF pauses and waits for your explicit approval before continuing.

---

## Session Management: Multi-Session Work and Recovery

Real research analyses take time -- often more time than a single Claude Code session can handle. DAAF is designed to handle this gracefully through its session state management system. Here's what you need to know.

### Understanding Context and Sessions

Claude Code operates within a context window that can be up to 1M tokens. However, quality can degrade well before the window is full, so DAAF enforces dual thresholds — both percentage-based and absolute token counts, whichever fires first. As DAAF works through a Full Pipeline analysis, delegating tasks to agents, receiving results, and coordinating the workflow, it gradually fills up this context. When it gets too full, Claude's performance degrades, and it becomes increasingly susceptible to erratic behavior due to **context rot**.

The exact points at which DAAF acts depend on the **context-quality threshold tier** assigned to the model you are running. DAAF detects the exact model identifier automatically and applies the right tier — you do not need to configure anything. The validated extended-horizon tier contains Claude Fable/Mythos models and exact GPT 5.6 Sol identifiers. Opus, Sonnet, unknown model IDs, every other GPT variant, and all other alternative-provider models use the conservative-default tier unless that exact model has been separately validated and registered.

Threshold-tier selection is version-specific and separate from the model's physical context-window size. For GPT 5.6 Sol, the terminal model slug must be exactly `gpt-5.6-sol` or `gpt-5.6-sol[1m]`; the identifier may be bare or may contain one or more provider path prefixes ending in `/`. Malformed left-boundary strings such as `xgpt-5.6-sol`, `foo-gpt-5.6-sol`, and `vendor/notgpt-5.6-sol` remain conservative, as do right-side suffix or trailing variants. GPT is not part of Claude's Fable/Mythos family; the two groups simply share the same validated thresholds. Terra, Luna, Pro, mini, chat, date snapshots, future variants, and trailing modifiers remain conservative unless separately validated. This means a wider GPT 5.6 variant can still have a 1,050,000-token physical window while DAAF applies the conservative quality thresholds.

To prevent context rot, DAAF monitors its own context utilization continuously and manages this proactively. The thresholds below trigger the same set of protective actions for every model — only the trigger points differ by threshold tier (percentage OR token count, whichever comes first):

| Threshold Tier | Membership | ELEVATED at | HIGH at | CRITICAL at |
|----------------|------------|-------------|---------|-------------|
| **Validated extended-horizon** | Claude Fable/Mythos models; exact terminal GPT 5.6 Sol model slugs, bare or provider-prefixed: `gpt-5.6-sol` or `gpt-5.6-sol[1m]` | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 400k tokens | ≥ 50% or ≥ 500k tokens |
| **Conservative-default** | Opus, Sonnet, unknown model IDs, every other GPT variant, and all other alternative-provider models unless individually validated and registered | ≥ 40% or ≥ 150k tokens | ≥ 60% or ≥ 200k tokens | ≥ 75% or ≥ 250k tokens |

| Status | What DAAF Does |
|--------|----------------|
| NOMINAL | Normal operation; no special action |
| ELEVATED | Starts delegating more work to subagents to keep the orchestrator's context lean |
| HIGH | Finishes the current work unit, updates STATE.md thoroughly, and warns you that a restart may be needed soon |
| CRITICAL | Finalizes STATE.md and recommends restarting the session |

### How Session Recovery Works

When a session needs to restart (whether due to context exhaustion, network interruption, or you simply closing your terminal), DAAF doesn't lose your progress. Here's why:

1. **STATE.md** captures the exact point where work stopped -- which stage, which script, what's been completed, what's next
2. **The Plan document** contains the full methodology and task sequence
3. **All scripts and data files** are already saved to disk
4. **LEARNINGS.md** captures any insights accumulated so far
5. **Session transcripts** are archived automatically when a session ends -- and if a session crashes before that happens, a recovery hook archives the orphaned transcript on the next session start, so no interaction records are lost

To resume a session, simply start a new Claude Code session and tell DAAF to pick up where it left off:

```
I need to resume the school poverty analysis we were working on.
The project folder is at research/2026-01-24_School_Poverty_Analysis/
```

DAAF will read STATE.md, understand where it stopped, and resume from that exact point. You don't need to re-explain your research question or re-run any completed stages.

**Reproducibility Verification mode note:** RV mode uses `Reproduction_Report.md` as its session state document instead of STATE.md. If an RV session is interrupted, the Reproduction Report contains a "Session Continuity" section with a restart prompt. The recovery process works the same way — start a new session and paste the restart prompt, and DAAF will pick up where it left off.

### How to Restart a Session

When DAAF determines that context is running low, it will do three things:

1. **Save progress** by updating STATE.md with everything completed so far
2. **Provide a restart prompt** -- a pre-written message that captures exactly where the work left off, what has been done, and what needs to happen next
3. **Tell you it's time to restart**

To resume, the steps are simple:

1. Type `/clear` in the Claude Code terminal to reset the session (this clears the context window but does not affect any files on disk)
2. Paste the restart prompt that DAAF provided
3. DAAF reads STATE.md, picks up where it left off, and continues working

That's it. The restart prompt does the heavy lifting of re-establishing context so you don't have to re-explain anything. If you closed your terminal entirely (or the session crashed), just start a new Claude Code session and point DAAF to the project folder -- it will read STATE.md and figure out where to resume.

### Tips for Multi-Session Work

- **Don't panic if a session ends mid-analysis.** This is undesired but not unexpected for complex analyses. The whole STATE.md system exists precisely for this reason.
- **A session restart is not a failure state.** We're constantly and deliberately toe-ing the line between "giving enough context for Claude to do a good job at what we're asking for" and "filling up the context so much that it gets confused and does weird stuff" to optimize our performance. The session restart is our way of maintaining that balance deliberately as a pressure valve.
- **Let DAAF finish its current "atomic unit" before stopping it as the context window begins to fill.** If DAAF is in the middle of executing a script and running QA, try to let it complete that cycle before stopping. Interrupting mid-script is recoverable but creates a messier restart.
- **You can always check progress.** At any point, you can ask DAAF: "What's the current status of the analysis?" and it'll tell you where things stand.
- **Complex analyses may take several sessions.** A nine-source, multi-year analysis with extensive transformations and multiple statistical tests can easily fill up multiple context windows. This is fine -- I've designed the system such that each session picks up seamlessly and as painlessly as possible from where the last one left off. But it definitely can be annoying doing it multiple times!

---

## Where Things Live in the Repository

You don't need to know what's in most of these directories -- the two that matter most to you day-to-day are `research/` (where your analyses live) and `user_reference/` (where the documentation lives). Everything else is DAAF's internal machinery, but here's a quick reference for what each part of the repository contains and who it's for:

| Directory | What's In It | Who It's For |
|-----------|-------------|-------------|
| `research/` | Your analysis projects -- notebooks, data, reports, scripts | **You** (this is where all your work lives) |
| `user_reference/` | User documentation (you're reading one right now) | **You** (human-written guides and FAQs) |
| `.claude/agents/` | Specialized agent protocols (14 behavioral definitions) | **DAAF** (and curious users who want to understand how agents work) |
| `agent_reference/` | Detailed workflow documentation, templates, validation rules | **DAAF** (internal reference material for the orchestrator and agents) |
| `.claude/skills/` | Skill definitions providing domain knowledge | **DAAF** (and users who want to create new skills) |
| `scripts/` | Shared utility scripts (`run_with_capture.sh`, `collect_session_logs.sh`, `generate_log_viewer.sh`, `launch_marimo.sh`, `launch_code_server.sh`) | **DAAF** (used from the DAAF root directory; not copied into projects) |
| `scripts/host/` (copied to your `daaf-docker/` folder during installation) | Host-side convenience scripts (`run_daaf`, `view_logs`, `view_notebooks`, `view_quarto`, `run_vscode`, `backup_daaf`, `restore_from_backup`, `rebuild_daaf`, `update_daaf` -- `.sh` and `.ps1` variants) | **You** (run from your `daaf-docker` folder on the host, outside the container) |

**Key insight for new users:** Everything you need to review, share, or reproduce is inside the project folder. You can copy the entire folder to a colleague and they'd have everything needed to understand and verify the analysis. That's the whole point of reproducibility.

### Browsing and Viewing Your Work

DAAF includes convenience scripts for viewing your files, notebooks, and session logs outside of the terminal. Run these from your `daaf-docker` folder on the host (i.e., outside the container):

- **Browse and edit project files:** `bash run_vscode.sh` (macOS/Linux) or `.\run_vscode.ps1` (Windows) -- opens a browser-based VS Code editor. You can preview Markdown reports and plans with `Shift+Ctrl+V`, read Python and R scripts with syntax highlighting, and inspect the Git history to see what changed and when. See [**03. Best Practices — Using the Browser-Based Code Editor**](03_best_practices.md#using-the-browser-based-code-editor) for more.
- **View interactive notebooks (Python):** `bash view_notebooks.sh` (macOS/Linux) or `.\view_notebooks.ps1` (Windows) -- opens marimo's notebook browser at [http://localhost:2718](http://localhost:2718), where you can browse and open any project notebook.
- **View Quarto documents (R):** `bash view_quarto.sh` (macOS/Linux) or `.\view_quarto.ps1` (Windows) -- renders an R project's Quarto (`.qmd`) notebook to a self-contained HTML file, copies it out to a `quarto_html/` folder on your host, and opens it in your browser. Run it with no argument to list available notebooks, or pass a project folder to render one.
- **View session logs:** `bash view_logs.sh` (macOS/Linux) or `.\view_logs.ps1` (Windows) -- opens the **DAAF Log Explorer**, an interactive timeline that shows orchestrator actions, subagent dispatches, and tool calls in your browser at [http://localhost:2719](http://localhost:2719). See the [Installation Guide — Viewing Session Logs](01_installation_and_quickstart.md#viewing-session-logs-in-your-browser) for details.

---

## Recommended Next Steps

- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
