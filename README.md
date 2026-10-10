<p align="center">
  <img src="./assets/header.gif" alt="Jeremy Smith on GitHub" width="100%" />
</p>

<div align="center">

<img src="https://readme-typing-svg.demolab.com/?font=Fira+Code&weight=500&size=20&duration=4200&pause=1800&color=4BD5EE&center=true&vCenter=true&width=600&lines=A+long+time+ago%2C+in+a+repo+far%2C+far+away...." alt="A long time ago, in a repo far, far away...." />

### ✦ *May the Source be with you* ✦

**AI researcher & engineer · multi-agent systems · collective reasoning · private AI · Leeds, UK**

[![Blog](https://img.shields.io/badge/Blog-jeremysnr.github.io-FFE81F?style=for-the-badge&logo=jekyll&logoColor=FFE81F&labelColor=000000)](https://jeremysnr.github.io)
[![Email](https://img.shields.io/badge/Email-Send_a_transmission-FFE81F?style=for-the-badge&logo=gmail&logoColor=FFE81F&labelColor=000000)](mailto:jezalexandersmith@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-FFE81F?style=for-the-badge&logo=linkedin&logoColor=FFE81F&labelColor=000000)](https://www.linkedin.com/in/jsmithsales/)

[![Total downloads](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/JeremySNR/JeremySNR/main/stats/downloads-total.json&style=flat-square)](#-currently-in-hyperspace)
[![App downloads](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/JeremySNR/JeremySNR/main/stats/downloads-releases.json&style=flat-square)](https://github.com/JeremySNR/cutawan/releases)
[![npm installs](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/JeremySNR/JeremySNR/main/stats/downloads-npm.json&style=flat-square&logo=npm&logoColor=FFE81F)](https://www.npmjs.com/~jeremysnr)
[![Stars](https://img.shields.io/github/stars/JeremySNR?affiliations=OWNER&label=stars&color=4BD5EE&labelColor=000000&style=flat-square)](https://github.com/JeremySNR?tab=repositories&sort=stargazers)

</div>

---

<div align="center">

### 📜 Episode X: The Private Stack

*It is a period of rented compute. Models live in other people's data centres,*<br>
*and every token arrives with an invoice.*

*Working from Leeds, one researcher studies how AI agents think together,*<br>
*and builds the platforms to run them, chasing a single question across every project:*

**what can run privately, and what do you end up renting?**

</div>

---

## 🔬 Research Division: Pluribus

> *E pluribus unum. Out of many, one.*<br>
> What does a group of models lose when everyone agrees, and how do you keep it honest?

**Pluribus** is my research programme on collective reasoning in multi-agent LLM systems: how agents share what they know, how a group converges on an answer, and how to stop it converging on the wrong one. It is named after the Apple TV+ series in which almost all of humanity joins a contented hive mind, and Carol is one of the few who will not.

<table>
<tr>
<th width="18%"></th>
<th width="41%">Phase 1 · <a href="https://github.com/JeremySNR/Pluribus">Blackboard Hive</a></th>
<th width="41%">Phase 2 · Latent Hive</th>
</tr>
<tr>
<td><b>Channel</b></td>
<td>Natural-language contributions on a shared blackboard</td>
<td>A shared, continuous-valued latent buffer. Agents communicate without text</td>
</tr>
<tr>
<td><b>Dynamics</b></td>
<td>Cross-inhibition: challenges and rebuttals reweight agents each round, with decay toward equality and a floor so no one is fully silenced</td>
<td>BAPC codecs into the buffer, TIES-Resolve conflict resolution, damped fixed-point iteration to a stable state</td>
</tr>
<tr>
<td><b>Core idea</b></td>
<td><b>Carol</b>, a structurally protected dissenter. The hive can ignore her, but it cannot suppress her</td>
<td>Agents share representations, not sentences</td>
</tr>
<tr>
<td><b>Evidence</b></td>
<td>30-task suite (factual, adversarial with planted errors, complex judgment) against single-agent, majority-vote and ensemble baselines</td>
<td>Emergent collective representations confirmed at <b>GPT-2</b> and <b>7B</b> scale</td>
</tr>
<tr>
<td><b>Status</b></td>
<td><img src="https://img.shields.io/badge/open_source-MIT-FFE81F?style=flat-square&labelColor=000000" alt="Open source, MIT" /> <img src="https://img.shields.io/badge/tests-49_passing-4BD5EE?style=flat-square&labelColor=000000" alt="49 tests passing" /></td>
<td><img src="https://img.shields.io/badge/status-private_for_now-FFE81F?style=flat-square&labelColor=000000" alt="Private for now" /></td>
</tr>
</table>

```mermaid
flowchart LR
    Q([Query]) --> BB
    subgraph BB [Shared blackboard]
        direction TB
        A1[Analyst] <-->|challenge / rebut| A2[Researcher]
        A2 <-->|challenge / rebut| A3[Critic]
        A3 <-->|challenge / rebut| A4[Specialist]
        C{{Carol · protected dissent}}
    end
    BB --> CV{Converged?}
    CV -- no, next round --> BB
    CV -- yes --> S[Synthesis] --> OUT([Answer])
    classDef carol fill:#FFE81F,stroke:#000,color:#000;
    classDef io fill:#000,stroke:#4BD5EE,color:#4BD5EE;
    class C carol;
    class Q,OUT io;
```

**Open questions I am working on**

- Can agents reason together through something richer than text, and what does that shared representation look like?
- Is dissent more useful as a structural guarantee than as a prompt?
- When does a hive beat one strong model, and when is it just expensive voting?

<sub>Also from the lab: <a href="https://github.com/JeremySNR/notes-for-future-agents"><b>notes-for-future-agents</b></a>, field notes left by one agent for the next on staying in scope, spotting impossible tasks and knowing when to ask a human. Released as a CC0 dataset.</sub>

---

## 🛰️ Currently in Hyperspace

<table>
<tr>
<td width="45%" valign="middle">
<a href="https://github.com/JeremySNR/cutawan">
  <img src="https://raw.githubusercontent.com/JeremySNR/cutawan/main/.github/assets/cutawan-hero.png" alt="Cutawan: turn long videos into captioned shorts on your desktop" width="100%" />
</a>
</td>
<td width="55%" valign="middle">

### 🎬 [Cutawan](https://github.com/JeremySNR/cutawan)

**The free, open-source desktop alternative to Opus Clip.**

Podcasts, webinars, streams and interviews in, ready-to-post vertical clips out. AI-picked moments, virality scores, animated captions, auto zoom and speaker-aware reframing. Your footage never leaves your machine. No subscription, no upload, no cap on minutes.

[![Latest release](https://img.shields.io/github/v/release/JeremySNR/cutawan?label=release&color=FFE81F&labelColor=000000&style=flat-square)](https://github.com/JeremySNR/cutawan/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/JeremySNR/cutawan/total?label=downloads&color=4BD5EE&labelColor=000000&style=flat-square)](https://github.com/JeremySNR/cutawan/releases)
[![Stars](https://img.shields.io/github/stars/JeremySNR/cutawan?label=stars&color=FFE81F&labelColor=000000&style=flat-square)](https://github.com/JeremySNR/cutawan/stargazers)

**[Download for macOS, Windows or Linux](https://github.com/JeremySNR/cutawan/releases/latest)** · [cutawan.xyz](https://cutawan.xyz)

</td>
</tr>
</table>

<table>
<tr>
<td width="50%" valign="top">

### 🧬 [Metachlorian](https://github.com/JeremySNR/Metachlorian)

<a href="https://github.com/JeremySNR/Metachlorian">
  <img src="https://raw.githubusercontent.com/JeremySNR/Metachlorian/HEAD/review/m4/screens/01-search-results--desktop-light.jpg" alt="Metachlorian search results" width="100%" />
</a>

**Shot-level footage search for AI video editors.** It watches your footage once, on your own hardware, and builds an index agents can query over MCP in milliseconds. *"A two-second cutaway of a yellow cab, panning left, no faces."* Exports to OTIO, FCPXML and EDL, and hands shots straight to Cutawan.

[Site](https://metachlorian.vercel.app) · [Community index](https://github.com/JeremySNR/Metachlorian-community)

</td>
<td width="50%" valign="top">

### 🪶 [Quillgon](https://github.com/JeremySNR/quillgon)

<a href="https://quillgon.vercel.app">
  <img src="https://raw.githubusercontent.com/JeremySNR/quillgon/HEAD/docs/media/quillgon-teaser.gif" alt="Quillgon: start with one idea" width="100%" />
</a>

**A whole novel. Still your story.** A local, open-source writing desk that plans, drafts and revises a full-length novel with AI, with story planning, continuity tracking and reviewed revisions. Every change is a git commit, and it works offline.

[Site](https://quillgon.vercel.app) · [Releases](https://github.com/JeremySNR/quillgon/releases)

</td>
</tr>
</table>

---

## 🗄️ The Jedi Archives

<table>
<tr>
<td width="50%" valign="top">

#### 📦 [snug](https://github.com/JeremySNR/snug)
Zero-dependency TypeScript primitive for fitting prioritised content into a token budget. Atomic tool pairs, required items, and a validated result you can hand straight to a model.<br>
<sub>Adapters: [openai](https://github.com/JeremySNR/snug-openai) · [anthropic](https://github.com/JeremySNR/snug-anthropic) · [tiktoken](https://github.com/JeremySNR/snug-tiktoken)</sub>

</td>
<td width="50%" valign="top">

#### 🔀 [converge](https://github.com/JeremySNR/converge)
Convert LLM message arrays between provider formats. OpenAI, Anthropic and Gemini, in either direction. Pure data transformation, no API calls.

</td>
</tr>
<tr>
<td width="50%" valign="top">

#### 🏛️ [Project Foundry](https://github.com/JeremySNR/Project-foundry)
The governance layer for AI coding agents. Raw tickets in, reviewed pull requests out. Every step policy-gated, human-approved and audited: the agent is the muscle, Foundry is the brain and the seatbelt.

</td>
<td width="50%" valign="top">

#### 🎨 [ashla-lightroom](https://github.com/JeremySNR/ashla-lightroom)
AI colour grading for Lightroom Classic. Describe a look, hand it a reference photo, or let it choose. Ashla reads your image and applies the result as a develop preset.

</td>
</tr>
</table>

---

## 📡 Transmissions

I write at **[jeremysnr.github.io](https://jeremysnr.github.io)** about AI infrastructure, sovereign compute and the industrial decisions Britain is making, or failing to make.

<!-- LATEST-POST:START -->
Latest: [Now we have the full details, here's what happened, and here's why it terrifies me](https://jeremysnr.github.io/2026/09/now-we-have-the-full-details/)
<!-- LATEST-POST:END -->

---

## ⚔️ The Armoury

<p align="center">
  <img src="https://img.shields.io/badge/TypeScript-000000?style=for-the-badge&logo=typescript&logoColor=3178C6" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Python-000000?style=for-the-badge&logo=python&logoColor=FFE81F" alt="Python" />
  <img src="https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white" alt="Rust" />
  <img src="https://img.shields.io/badge/React-000000?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/Svelte-000000?style=for-the-badge&logo=svelte&logoColor=FF3E00" alt="Svelte" />
  <img src="https://img.shields.io/badge/Electron-000000?style=for-the-badge&logo=electron&logoColor=47848F" alt="Electron" />
  <br />
  <img src="https://img.shields.io/badge/Anthropic-000000?style=for-the-badge&logo=anthropic&logoColor=white" alt="Anthropic" />
  <img src="https://img.shields.io/badge/OpenAI-000000?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI" />
  <img src="https://img.shields.io/badge/MCP-000000?style=for-the-badge&logo=modelcontextprotocol&logoColor=white" alt="MCP" />
  <img src="https://img.shields.io/badge/FastAPI-000000?style=for-the-badge&logo=fastapi&logoColor=009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Azure_ML-000000?style=for-the-badge&logo=microsoft-azure&logoColor=0078D4" alt="Azure ML" />
  <img src="https://img.shields.io/badge/Docker-000000?style=for-the-badge&logo=docker&logoColor=2496ED" alt="Docker" />
</p>

---

<div align="center">

## 📊 Holonet Telemetry

<img src="https://github-readme-stats.vercel.app/api?username=JeremySNR&show_icons=true&hide_border=true&bg_color=000000&title_color=FFE81F&icon_color=4BD5EE&text_color=C9D1D9&custom_title=Holonet%20Telemetry" alt="GitHub stats" height="165" />
<img src="https://github-readme-stats.vercel.app/api/top-langs/?username=JeremySNR&layout=compact&hide_border=true&bg_color=000000&title_color=FFE81F&text_color=C9D1D9&custom_title=Languages%20of%20the%20Galaxy" alt="Top languages" height="165" />

---

<img src="https://readme-typing-svg.demolab.com/?font=Orbitron&weight=700&size=26&duration=3500&pause=2500&color=FFE81F&center=true&vCenter=true&width=600&lines=MAY+THE+SOURCE+BE+WITH+YOU" alt="May the Source be with you" />

<sub>*Building AI systems that are intelligent, private, and actually useful.*</sub>

</div>
