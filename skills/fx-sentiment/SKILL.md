---
name: fx-sentiment
description: Research trader sentiment and competing market narratives on the public web for FX, gold and oil. Use for crowd views, shifts in expectations, trade ideas sourced from forums or social posts, or a market setup whose thesis depends on public expectations. Arabic triggers include معنويات السوق، مزاج المتداولين، ابحث في المنتديات، وتوصية من آراء المتداولين.
---

# FX sentiment research

Use the host agent's web search and page-reading tools, or approved platform connectors. This skill can run independently of MT5 and of the other FX skills. A quote-only request needs only the pricing capability. For an existing idea, research the contested claim or the changes since the prior snapshot. When browsing is unavailable, analyze supplied posts or report the coverage gap.

## Define the question and search

Record the instrument, horizon and decision time. Distinguish spot gold, local retail gold, gold futures and mining equities. Interpret EUR/USD direction relative to the dollar. Search in the user's language and other relevant market languages. Include neutral instrument queries, competing theses, desk commentary and trader discussions. Adapt the lookback to the horizon and event, and note which communities and periods were reachable. With historical queries, include only information demonstrably public by the cutoff. Exclude a later edit from historical evidence unless its earlier wording can be verified.

Open the original thread or post and read the surrounding discussion. Search snippets alone are discovery leads. Preserve a direct link and publication time, or mark the time uncertain. Attribute what the author expects, in which instrument and horizon, under what condition, and why. Distinguish a reported position from a prediction, a quotation from the author's own view, and an emotional reaction from a directional view. Check market-moving factual premises against their original release when available.

## Combine the evidence

Group copies, syndications and cross-posts by identifiable origin. Track both the number of distinct arguments and their amplification. Analysts reacting independently to the same release may show broad agreement, while the release remains one underlying fact. Mark uncertain independence. Keep opposing views visible. Avoid reading an indexed sample as representative of all investors or inferring actual positions from likes.

Look for the dominant explanation, the best supported competing explanation, and changes since the last comparable observation. Claim a shift only with an earlier comparable sample. Report any counts with their denominator, selection method and time window. Two independent, timely sources may support an idea. Additional sources add weight when they bring new observations or genuinely distinct analysis. The number of mentions does not supply a calibrated win probability.

## Report or propose a trade idea

For a sentiment request return the direction, disagreement, horizon, window, coverage and linked evidence in the user's language. For an idea request, a thesis may originate in the web research itself. State the proposed direction or decision to wait, why the evidence supports it, the strongest objection, what would activate or invalidate it, and its time horizon. Choose the relevant setup family, such as continuation after a pullback, range rejection, breakout and retest, or repricing after a catalyst. These are hypotheses to assess, not mandatory successive stages.

Where the argument depends on price behavior, identify the matching instrument and timestamp from a suitable market source. Express unverified numerical levels as attributed claims, or give an observable condition without inventing levels. A crowded narrative alone cannot establish that price will reverse. If the scale of disagreement changes the decision, show the competing scenario. If source access is sparse, disclose precisely what the available sample supports.

When handing an idea to another skill, pass its instrument, horizon, as-of time, strategy, directional thesis, activation, invalidation, original links and coverage limitations. Carry the existing idea identifier when supplied. For later evaluation, freeze the evidence as it was available at decision time and compare outcomes for the same setup with and without the sentiment input.
