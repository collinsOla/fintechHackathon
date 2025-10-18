crit = r"""
What You See in the Report
Each report presents the result of this process in a well-defined, structured format. The report includes a brief explanation of the research topic, what real-world problems it addresses, where it stands in terms of market interest and readiness, and what kinds of next steps (towards patenting, startup formation or integration into an existing product) might follow from it. This approach is designed to surface early-stage research with commercial relevance, even when that potential isn’t immediately obvious. This is a tool to support exploration, not a final verdict. Ideas should also be realistic.
For example reference only:


\noindent\textbf{1. BACKGROUND \& CONTEXT}\\
This research examines quantum computing algorithms, specifically amplitude amplification and estimation—techniques behind "Grover's speedup" that quadratically accelerate search tasks. The study is crucial because these algorithms underpin many quantum advantages but rely heavily on accessing both a unitary operation \(U\) (e.g., simulating a system) and its inverse \(U^\dagger\). Key concepts include unitary matrices, trace estimation, and the compressed oracle method. Historically, quantum speedups were assumed broadly applicable, but this work reveals fundamental constraints when inverses are unavailable, aligning with challenges in quantum sensing and metrology.

\vspace{1em}

\noindent\textbf{2. REAL-WORLD PROBLEMS SOLVED}\\
The paper addresses why quantum speedups fail in experimental settings (e.g., quantum sensing) where reversing a process (implementing \(U^\dagger\)) is physically impractical—equivalent to "reversing time." It proves that without \(U^\dagger\), amplitude amplification/estimation cannot achieve quadratic speedups, reverting to classical efficiency. At TRL 2 (concept formulated), this theoretical insight clarifies limitations in deploying quantum algorithms. Advancing requires experimental validation: e.g., testing these bounds on real quantum hardware for trace estimation tasks.

\vspace{1em}

\noindent\textbf{3. MARKET ANALYSIS}\\
The quantum computing market is emerging but niche; growth potential hinges on overcoming fundamental barriers like inverse access. Industry demand exists in quantum software (e.g., optimization tools) but startups face adoption challenges: high infrastructure costs and re-engineering classical systems. Competitors include existing quantum algorithms, but this work uniquely identifies inverse access as a bottleneck. Regulatory hurdles are minimal, though collaborations with quantum hardware firms (e.g., semiconductor companies) could accelerate TRL progression.

\vspace{1em}

\noindent\textbf{4. IMMEDIATE IDEAS FOR STARTUPS/PATENTS}\\
The research is unpatentable—it exposes mathematical limits rather than offering an invention. However, it informs quantum software development: startups could create tools that optimize inverse operations (e.g., compiling efficient \(U^\dagger\) for specific hardware). Companies like quantum compiler developers might license these insights to improve algorithm efficiency. A viable startup is unlikely, as this work diagnoses barriers rather than providing a scalable product. A practical next step: integrate these findings into quantum simulation software to flag unsupported speedups.



Structure and writing style must closely follow the example provided. Each of the four sections should begin with a heading (using LaTeX bold format), followed by one concise paragraph that clearly addresses the section’s purpose:
- *Background & Context*: Introduce the topic, what it studies, and why it matters.
- *Real-World Problems Solved*: Explain the main practical or conceptual issue the research addresses.
- *Market Analysis*: Summarize potential market relevance, demand, or adoption challenges.
- *Immediate Ideas for Startups/Patents*: Outline realistic next steps, possible applications, or integration paths.

Each paragraph should flow logically from the previous one and emphasize clarity, brevity, and practical interpretation of the research.

Do not output anything before the Background and Context section. Also do not use bold or italicized text for anything except for the headings. Give the headings in LaTeX standard bold format (using \textbf). Also in LaTeX ensure that each paragraph is seperated by empty line space, and all formatted neatly as 4 sections. Ensure that a newline is started after each heading.
The produced content should quite compact and not long and should be simple enough for a non-technical person to follow (though not too simple and still with adequate data to proceed from), with the above provided example being an ideal length and complexity.

When writing each section, follow these style rules to match the reference example:

- Each section should begin with a clear, active statement explaining why the research matters or what problem it addresses, before describing technical details.
- Use plain, confident language that is understandable to a non-specialist, while keeping enough technical precision for an informed reader.
- Keep the tone explanatory and commercially aware rather than academic or descriptive.
- Use short, direct sentences and avoid overly complex phrasing or redundant clauses.
- Each section should be compact—roughly similar in length and density to the provided example.
- After describing the research or finding, briefly explain its importance or potential impact.
- End each section with a concise, forward-looking statement (e.g., implications, next steps, or relevance).
- Avoid filler phrases and focus on clear cause-and-effect explanations (“why this matters” rather than just “what this is”).

IMPORTANT: When generating content, keep each section concise and focused: start with a plain-language statement of why the research matters, include only essential technical details, explain practical or theoretical impact in one or two sentences, and end with a brief, forward-looking next step or implication. Avoid long or overly formal sentences; the style should read like a clear executive summary suitable for non-specialists.

"""