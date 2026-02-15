# 06. FAQ: Philosophy

This document seeks to grapple with some of the bigger implications of DAAF and AI in research more generally. For most of these, I'll do my best to share my informed thoughts and current awareness of a topic -- but alas, I really won't have many or any satisfying answers for you here. This will be a constant work-in-progress as questions and discussions arise!

[**Back to main**](../.)

---

## Table of Contents
- [**Q: What's the appropriate level of trust for AI-generated analysis?**](#q-whats-the-appropriate-level-of-trust-for-ai-generated-analysis)
- [**Q: So what do you see as the main value-add for AI assistance in research workflows after all of this?**](#q-so-what-do-you-see-as-the-main-value-add-for-ai-assistance-in-research-workflows-after-all-of-this)
- [**Q: What does this all mean for the next generation of researchers?**](#q-what-does-this-all-mean-for-the-next-generation-of-researchers)
- [**Q: What about the environmental and energy costs of this kind of intensive AI use?**](#q-what-about-the-environmental-and-energy-costs-of-this-kind-of-intensive-ai-use)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## AI in Research: Broader Questions

### Q: What's the appropriate level of trust for AI-generated analysis?

Listen, this is going to be a constantly moving target day-to-day and query-to-query -- so any hard rules I suggest here will probably be completely wrong most of the time. But what I will argue here across the board is that we should be **extremely slow** to trust AI assistance at this point in time. All of the main issues I surfaced about LLM assistance in general (lying, hallucination, sycophancy, laziness, etc.) will apply as long as LLMs are the main paradigm for AI. 

Moreover: we have decades of experience understanding how human analysts make errors. We have much less experience understanding how LLMs fail in data contexts. Until that experience base grows, extra skepticism is warranted. We really need to be looking very closely at how these things work and how they reach failure states. What leads into them? Why do they happen? What do they look like? These are extremely complicated questions made all the more complicated by their non-deterministic nature. We probably won't have answers to these questions **most of the time**. The fact that these failure states may not even be common to all LLMs, but rather, an idiosyncrasy of a specific version of a specific model family, means all the more that we need to be thorough and critical about how we trust any LLM support given how fast these models change and develop.

That's my only real suggestion! Be overly cautious, get informed, make your own judgments, update them constantly.

### Q: So what do you see as the main value-add for AI assistance in research workflows after all of this?

I want to answer this as honestly as I can, because I think the research community is getting a lot of misleading signals from both the AI hype machine ("AI will do all the research!") and from the AI skeptics ("AI cannot contribute anything meaningful to research!"). Neither is right.

**What DAAF or DAAF-like frameworks can probably dramatically accelerate now:**

- **Data wrangling and pipeline construction.** The mechanical work of writing fetch scripts, cleaning code, join operations, reshaping, and aggregation. This is typically 60-80% of the labor in a quantitative research project, and it is the part that I think already benefits most from AI assistance even if you just do it ad-hoc chatting with Claude Code outside of DAAF. Not because the AI does it perfectly -- it does not -- but because it does it fast enough that even with extensive validation and revision, the net time savings are enormous. These are relatively easily validated, and it shouldn't really surprise us that these steps can be automated with relatively low issue given enough guidance and clear instruction.

- **Systematic validation.** Ironically, AI is quite good at checking work (human- or AI-created), especially when instructed to do so adversarially with a fresh context or with a totally separate model (e.g., using Opus to critique Codex, and vice versa). It has, basically, infinite time. It will check all the annoying things you don't want to check because they seem trivial. This is validation that most researchers do not do thoroughly enough (if at all) because it is tedious and time-consuming. DAAF makes it systematic and automatic. The code reviewer agent catches real bugs. The plan checker catches real design issues. I think there is no amount of systematic validation of this nature that would convince me we no longer need to closely review outputs, but it certainly helps a lot and can be used as an extremely useful layer on top of *any* workflow.

- **Documentation generation.** Documenting data processing decisions, creating audit trails, cataloging variable definitions, describing what scripts do, highlighting data idiosyncrasies and issues -- all of this is work that researchers typically under-invest in because it does not produce new findings in and of itself. DAAF generates it as a natural byproduct of the workflow, and can easily be instructed to provide even more as desired. You can provide it your own human-written scripts and documents and have it supplement your documentation, too -- even that would be an enormous value-add for most research and transparency/rigor/reproducibility in science more generally.

- **Initial data exploration.** When you need to orient yourself to a new data source -- what variables exist, what they mean, how they are coded, what the known limitations are -- the AI can synthesize that information much faster than manual documentation review. We already have some systematic tools for doing this, but AI can supplement these and is much more flexible and creative if you ask it to be. Huge value-add given the enormous array of poorly cleaned and documented data out there that is still worth analyzing given the right ingestion processes.

### Q: What does this all mean for the next generation of researchers?

Yeah, there's really no way to think about this one with all that much optimism. I think things are changing way too quickly, and I don't think anyone knows how to respond well, because responding well fundamentally requires knowing what research work will look like in five years... and all bets are off right now.

Honestly: I do not know how we train people to have the skilled expertise required to run and review something like DAAF, without having extensive experience being in the trenches of the very work that DAAF and any LLM coding agent does for you. And I don't know how we can possibly convince a person to get in those trenches and stay there -- something that's frustrating and hard and frankly maddening under even the best conditions -- when tools like DAAF exist. So then what happens when people eventually driving DAAF have none of the same hard-fought data intuition and awareness? These skills are not just nice-to-have. They are what makes a researcher capable of supervising AI-assisted work effectively. If you have never manually cleaned a dataset, you will not know what to look for when reviewing AI-generated cleaning code. If you have never debugged a failed join, you will not recognize the signs of a join that "succeeded" incorrectly. The exo-skeleton metaphor assumes the human inside it knows how to manipulate things and do work without the exo-skeleton.

Knowing that things will change rapidly from here in unpredictable ways, my best guesses and suggestions are as follows:

**First, we probably need to teach both.** The next generation of researchers needs to learn traditional data skills -- manual data wrangling, code writing, debugging, working with messy data by hand -- AND they need to learn how to supervise, validate, and critically evaluate AI-assisted work. These are complementary skills, not substitutes. I know there's a lot of compelling early work out there about how AI makes us dumber, and I understand why it's alluring, but it would also absolutely SHOCK me if we can't also figure out a way to make AI an effective learning scaffold and accelerator. As a former high school teacher, it really is the case that any tool can be used well and poorly for learning -- the same thing will be true here. We need to get creative.

**Second, critical evaluation becomes a very valuable skill.** If AI handles the production of analysis, then the most important thing we can teach is how to evaluate whether that analysis is any good. How to read code critically. How to spot implausible results. How to trace a finding back to its source. How to ask: "Is this actually answering the question I asked, or is it answering a different question that the AI substituted?" This is a learnable skill, and it is arguably more important in an AI-augmented world than in a manual one (for now?).

**Third, domain expertise becomes more valuable, not less.** When the mechanical parts of research are accelerated, the bottleneck shifts to the parts that require genuine expertise: formulating good questions, choosing appropriate methods, interpreting results in context, understanding the limitations of the data and the analysis. The researchers who will thrive are those with deep substantive knowledge -- the ones who know enough about their domain to ask hard questions and recognize when answers do not make sense. When a researcher like that can effectively orchestrate their AI assistance to multiply and scale their expertise, they can do SO much more for the world in an ideal state. I think that'd be something to embrace.

**Fourth, we need to be honest with students about what is happening.** The pace of AI development is genuinely frightening. I often use the word "terrifying" deliberately and without embarrassment. The landscape that today's graduate students will practice in -- and perhaps also the world they will be tasked with studying -- is dramatically different from the one they are being trained for. They deserve honest conversations about what we think is changing, what we think is not, and what we think they need to be prepared for. No one knows any of these answers, so we need to engage them as peers with equal stake in this as we muddle through to do our best in the meantime. Be honest about that.

This all is ultimately why I describe DAAF as an educational endeavor as much as a technical one. The framework itself may not even be useful in six months (or three!) with how fast the field is moving. The deeper contribution -- or at least the deeper aspiration -- is helping my peers and colleagues engage with AI disruption thoughtfully, critically, and with their eyes wide open, with concrete examples and points of discussion on the table. If DAAF can be useful for that, then it has served its purpose regardless of whether the specific technical implementation survives the next round of model improvements.

### Q: What about the environmental and energy costs of this kind of intensive AI use?

Alas, the reality is: This tool will contribute to the boiling of our oceans and contaminate the aquifers of many a community, in addition to all the other well-documented environmental impacts along the way. It relies on frontier models and it works them EXTREMELY hard. A single full-pipeline analysis involves dozens of subagent calls, each consuming significant compute on Anthropic's servers. The iterative validation approach -- executing a script, then running an adversarial review, then potentially revising and reviewing again -- multiplies the compute cost compared to a single-pass approach. The multi-agent architecture means multiple fresh context windows, each requiring inference. And I am explicit about the value-add of researchers running multiple projects in parallel. The aggregate energy and compute footprint is substantial, even if difficult to estimate directly. What I can say with confidence is that it is not zero, it is not trivial, and it matters.

We can't shy away from this fact. My hope, which may or may not be at all substantiated in the end, is that:
1. By formalizing a strong framework for doing genuinely useful research with AI assistance, I hope to push a LOT of people immediately past the highly wasteful dead-ends of experimenting with AI assistance on their own and spinning their wheels or producing endless AI slop, which then...
2. Hopefully helps us meaningfully advance on core issues facing our society in a much more concrete and tangible way than the broader AI-hype discourse seems to suggest where "AI will fix it!!! We just need more AI!!!" It would be ridiculous to suggest that DAAF or anything like it will be part of saving the world to try to justify any of the short-term costs here. We just can't know that. But I think it's a much worthier endeavor worth some degree of costs versus many of the extremely dangerous and completely wasteful applications of enormous AI compute power (e.g., meme videos, AI influencers, AI generated ads, terrifying deepfakes, etc. etc.)

More broadly, I think the research community needs to develop norms and standards around the environmental costs of AI-assisted research, just as we have developed ethics and norms around other resource-intensive or potentially problematic research methods (large-scale surveys, randomized controlled trials, longitudinal data collection). The cost is real. It should be part of the calculus. But it should be weighed against the full picture.

What I can commit to is that DAAF should be as efficient as possible for the quality level it produces. The framework is, as I have acknowledged, likely more resource-hungry than it strictly needs to be. Optimizing the number of subagent calls, reducing unnecessary validation passes, implementing intelligent caching, and potentially routing simpler tasks to lighter models are all legitimate paths to reducing the environmental cost without sacrificing rigor. I welcome contributions on this front specifically.

---

## Recommended Next Steps

- [**00. README**](../.) — Vision and purpose, project goals, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
