# Source manifest — 2026-04-15

Generated at: 2026-04-15T09:15:57.271273+00:00
Profile: daily
Relevant source count: 16

## 1. China’s edge over US in AI world models: abundant data, faster deployment, executive says
- Domain: scmp.com
- URL: https://www.scmp.com/tech/big-tech/article/3350062/chinas-edge-over-us-ai-world-models-abundant-data-faster-deployment-executive-says
- Relevance score: 16.0
- Published: Tue, 14 Apr 2026 12:00:10 +0000
- Summary: China’s world models are benefiting from early integration with the country’s strong industrial base, which gives the domestic ecosystem greater momentum than that of the US, according to an executive at a leading Chinese world model start-up. World models simulate 3D environments and physical dynamics, and are expected to help train the next generation of physical artificial intelligence applications, including robots and autonomous vehicles. Wang Xiaofeng, an algorithm partner at GigaAI, said...
- Extract: [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/search?module=masthead&pgtype=article) [Big Tech](https://www.scmp.com/tech/big-tech) - All [Big Tech](https://www.scmp.com/tech/big-tech) China’s AI world model edge: abundant data and faster deployment, executive says [](https://www.scmp.com/?module=masthead&pgtype=article) SIGN IN Advertisement [Artificial intelligence](https://www.scmp.com/topics/artificial-intelligence?module=breadcrumb&pgtype=article) [Tech](https://www.scmp.com/tech?module=breadcrumb&pgtype=article)[Big Tech](https://www.scmp.com/tech/big-tech?module=breadcrumb&pgtype=article) # China’s edge over US in AI world models: abundant data, faster deployment, executive says China’s stron

## 2. RePAIR: Interactive Machine Unlearning through Prompt-Aware Model Repair
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12820
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12820v1 Announce Type: cross Abstract: Large language models (LLMs) inherently absorb harmful knowledge, misinformation, and personal data during pretraining on large-scale web corpora, with no native mechanism for selective removal. While machine unlearning offers a principled solution, existing approaches are provider-centric, requiring retraining pipelines, curated retain datasets, and direct intervention by model service providers (MSPs), thereby excluding end users from controlling their own data. We introduce Interactive Machine Unlearning (IMU), a new paradigm in which users can instruct LLMs to forget targeted knowledge through natural language at inference time. To realize IMU, we propose RePAIR, a prompt-aware model repair framework comprising (i) a watchdog model for unlearning intent detection, (ii) a surgeon model for generating repair procedures, and (iii) a patient model whose parameters are updated autonomously. At the core of RePAIR, we develop Steering Through Activation Manipulation with PseudoInverse (STAMP), a training-free, single-sample unlearning method that redirects MLP activations toward a refusal subspace via closed-form pseudoinverse updates.

## 3. Generation-Augmented Generation: A Plug-and-Play Framework for Private Knowledge Injection in Large Language Models
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2601.08209
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2601.08209v4 Announce Type: replace Abstract: In domains such as materials science, biomedicine, and finance, high-stakes deployment of large language models (LLMs) requires injecting private, domain-specific knowledge that is proprietary, fast-evolving, and under-represented in public pretraining. However, the two dominant paradigms for private knowledge injection each have clear drawbacks: fine-tuning is expensive to iterate under continual updates that can induce catastrophic forgetting and general-capability regression; retrieval-augmented generation (RAG) keeps the base model intact but remains brittle in specialized private corpora due to chunk-induced evidence fragmentation, retrieval mismatch, and long-context pressure. Inspired by how multimodal LLMs align heterogeneous modalities into a shared semantic space, we propose Generation-Augmented Generation (GAG), which treats private expertise as an auxiliary modality and injects it into a frozen base model through a compact, constant-budget latent interface. Concretely, GAG distills question-conditioned specialist knowledge from lightweight domain experts into multi-slot latent memories, integrates multi-layer expert si

## 4. Polynomial Expansion Rank Adaptation: Enhancing Low-Rank Fine-Tuning with High-Order Interactions
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.11841
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.11841v1 Announce Type: new Abstract: Low-rank adaptation (LoRA) is a widely used strategy for efficient fine-tuning of large language models (LLMs), but its strictly linear structure fundamentally limits expressive capacity. The bilinear formulation of weight updates captures only first-order dependencies between low-rank factors, restricting the modeling of nonlinear and higher-order parameter interactions. In this paper, we propose Polynomial Expansion Rank Adaptation (PERA), a novel method that introduces structured polynomial expansion directly into the low-rank factor space. By expanding each low-rank factor to synthesize high-order interaction terms before composition, PERA transforms the adaptation space into a polynomial manifold capable of modeling richer nonlinear coupling without increasing rank or inference cost. We provide theoretical analysis demonstrating that PERA offers enhanced expressive capacity and more effective feature utilization compare to existing linear adaptation approaches. Empirically, PERA consistently outperforms state-of-the-art methods across diverse benchmarks. Notably, our experiments show that incorporating high-order nonlinear compon

## 5. AutoSurrogate: An LLM-Driven Multi-Agent Framework for Autonomous Construction of Deep Learning Surrogate Models in Subsurface Flow
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.11945
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.11945v1 Announce Type: new Abstract: High-fidelity numerical simulation of subsurface flow is computationally intensive, especially for many-query tasks such as uncertainty quantification and data assimilation. Deep learning (DL) surrogates can significantly accelerate forward simulations, yet constructing them requires substantial machine learning (ML) expertise - from architecture design to hyperparameter tuning - that most domain scientists do not possess. Furthermore, the process is predominantly manual and relies heavily on heuristic choices. This expertise gap remains a key barrier to the broader adoption of DL surrogate techniques. For this reason, we present AutoSurrogate, a large-language-model-driven multi-agent framework that enables practitioners without ML expertise to build high-quality surrogates for subsurface flow problems through natural-language instructions. Given simulation data and optional preferences, four specialized agents collaboratively execute data profiling, architecture selection from a model zoo, Bayesian hyperparameter optimization, model training, and quality assessment against user-specified thresholds. The system also handles common fa

## 6. Models Know Their Shortcuts: Deployment-Time Shortcut Mitigation
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12277
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12277v1 Announce Type: new Abstract: Pretrained language models often rely on superficial features that appear predictive during training yet fail to generalize at test time, a phenomenon known as shortcut learning. Existing mitigation methods generally operate at training time and require heavy supervision such as access to the original training data or prior knowledge of shortcut type. We propose Shortcut Guardrail, a deployment-time framework that mitigates token-level shortcuts without access to the original training data or shortcut annotations. Our key insight is that gradient-based attribution on a biased model highlights shortcut tokens. Building on this finding, we train a lightweight LoRA-based debiasing module with a Masked Contrastive Learning (MaskCL) objective that encourages consistent representations with or without individual tokens. Across sentiment classification, toxicity detection, and natural language inference under both naturally occurring and controlled shortcuts, Shortcut Guardrail improves overall accuracy and worst-group accuracy over the unmitigated model under distribution shifts while preserving in-distribution performance.

## 7. Token Encoding for Semantic Recovery
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12931
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12931v1 Announce Type: cross Abstract: Token-based semantic communication is promising for future wireless networks, as it can compact semantic tokens under very limited channel capacity. However, harsh wireless channels often cause missing tokens, leading to severe distortion that prevents reliable semantic recovery at the receiver. In this article, we propose a token encoding framework for robust semantic recovery (TokCode), which incurs no additional transmission overhead and supports plug-and-play deployment. For efficient token encoder optimization, we develop a sentence-semantic-guided foundation model adaptation algorithm (SFMA) that avoids costly end-to-end training. Based on simulation results on prompt-based generative image transmission, TokCode mitigates semantic distortion and can approach the performance upper-bound, even under harsh channels where 40% to 60% of tokens are randomly lost.

## 8. QuarkMedSearch: A Long-Horizon Deep Search Agent for Exploring Medical Intelligence
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12867
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12867v1 Announce Type: new Abstract: As agentic foundation models continue to evolve, how to further improve their performance in vertical domains has become an important challenge. To this end, building upon Tongyi DeepResearch, a powerful agentic foundation model, we focus on the Chinese medical deep search scenario and propose QuarkMedSearch, systematically exploring a full-pipeline approach spanning medical multi-hop data construction, training strategies, and evaluation benchmarks to further push and assess its performance upper bound in vertical domains. Specifically, for data synthesis, to address the scarcity of deep search training data in the medical domain, we combine a large-scale medical knowledge graph with real-time online exploration to construct long-horizon medical deep search training data; for post-training, we adopt a two-stage SFT and RL training strategy that progressively enhances the model's planning, tool invocation, and reflection capabilities required for deep search, while maintaining search efficiency; for evaluation, we collaborate with medical experts to construct the QuarkMedSearch Benchmark through rigorous manual verification. Experimen

## 9. Chinese robotics firms focus on quadrupeds as major revenue drivers
- Domain: scmp.com
- URL: https://www.scmp.com/tech/tech-trends/article/3350071/chinese-robotics-firms-focus-quadrupeds-major-revenue-drivers
- Relevance score: 11.0
- Published: Tue, 14 Apr 2026 23:00:19 +0000
- Summary: Chinese robotics companies are increasingly banking on quadruped robots as major revenue drivers, a trend highlighted by AgiBot’s recent decision to spin out its four-legged robotics unit into a new subsidiary called AgiQuad, and Amap’s coming launch of a quadruped model. The move by AgiBot was intended to drive large-scale growth so that the unit would not “live in the shadow of the humanoid robot giant”, Qiu Heng, chief operating officer of the new subsidiary, said at a media briefing last...
- Extract: Edition: International [](https://www.scmp.com/mynews) [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/search?module=masthead&pgtype=article) [Tech Trends](https://www.scmp.com/tech/tech-trends) - All [Tech Trends](https://www.scmp.com/tech/tech-trends) Chinese robotics firms focus on quadrupeds as major revenue drivers [](https://www.scmp.com/?module=masthead&pgtype=article) 1 SIGN IN Advertisement [Robotics](https://www.scmp.com/topics/robotics?module=breadcrumb&pgtype=article) [Tech](https://www.scmp.com/tech?module=breadcrumb&pgtype=article)[Tech Trends](https://www.scmp.com/tech/tech-trends?module=breadcrumb&pgtype=article) # Chinese robotics firms focus on quadrupeds as major revenue drivers The

## 10. AGIBOT and Longcheer Technology Achieve World's First Embodied AI Deployment in Consumer Electronics Precision Manufacturing Mass-Production Line - Utusan Malaysia
- Domain: utusan.com.my
- URL: https://news.google.com/rss/articles/CBMinwJBVV95cUxPcW4xc0ZWVEY5VmNrUlhVRjE1VkZwSml3M2plY0RFeEZSRWRQVXBtcWVDSUo4TmpwYV9xSFhVMWttYnoxWFZjbEtTaW4yaFNULW5lNTlIWWFHbDgxcUh6WEM2czZSMER2MlpOVGVmd0VaNURFMU9VOVZqOGR1aEVyM0RIMGpyYlFOelg2b2dzeVhJZ2dNSHdLZGRtY2c1SXFNWERqWTRWOUFoVm56QkUzWUdqTXFVaS01QThxWGRGdnBIWkhwakVLWFZCbk15Y3VMMHVOd2ZteVBZMm9MdG9VUGxGTTBpY2lyZ1BVY2VucVJBdGZlRjlSeTFNQkdTcmdRM0kxZldNTlNQY2d4WE9XeDZDd2RTVkE1aFN0cmpzTQ
- Relevance score: 6.5
- Published: Tue, 14 Apr 2026 23:09:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMinwJBVV95cUxPcW4xc0ZWVEY5VmNrUlhVRjE1VkZwSml3M2plY0RFeEZSRWRQVXBtcWVDSUo4TmpwYV9xSFhVMWttYnoxWFZjbEtTaW4yaFNULW5lNTlIWWFHbDgxcUh6WEM2czZSMER2MlpOVGVmd0VaNURFMU9VOVZqOGR1aEVyM0RIMGpyYlFOelg2b2dzeVhJZ2dNSHdLZGRtY2c1SXFNWERqWTRWOUFoVm56QkUzWUdqTXFVaS01QThxWGRGdnBIWkhwakVLWFZCbk15Y3VMMHVOd2ZteVBZMm9MdG9VUGxGTTBpY2lyZ1BVY2VucVJBdGZlRjlSeTFNQkdTcmdRM0kxZldNTlNQY2d4WE9XeDZDd2RTVkE1aFN0cmpzTQ?oc=5" target="_blank">AGIBOT and Longcheer Technology Achieve World's First Embodied AI Deployment in Consumer Electronics Precision Manufacturing Mass-Production Line</a>&nbsp;&nbsp;<font color="#6f6f6f">Utusan Malaysia</font>

## 11. Fire Service Essay Competition returns with artificial intelligence prompt - International Fire & Safety Journal
- Domain: internationalfireandsafetyjournal.com
- URL: https://news.google.com/rss/articles/CBMidkFVX3lxTE91SmtST2luTER3eVc4NkFqZHdKaV9MNC1oa1FJMGNaNmRrdlJXRHoxdXc4cTc0SE1PV2NlRnpGQkFVcjA2WkE0VkpwNTlWUy1nUFM4S2RkbVVhaERGc2ZFemtIaU1vY2h5MVBLTVNrclpWdFBCa3c
- Relevance score: 6.0
- Published: Wed, 15 Apr 2026 09:06:06 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMidkFVX3lxTE91SmtST2luTER3eVc4NkFqZHdKaV9MNC1oa1FJMGNaNmRrdlJXRHoxdXc4cTc0SE1PV2NlRnpGQkFVcjA2WkE0VkpwNTlWUy1nUFM4S2RkbVVhaERGc2ZFemtIaU1vY2h5MVBLTVNrclpWdFBCa3c?oc=5" target="_blank">Fire Service Essay Competition returns with artificial intelligence prompt</a>&nbsp;&nbsp;<font color="#6f6f6f">International Fire & Safety Journal</font>

## 12. Nvidia releases open AI models for quantum computing tasks — 'Ising' said to be 2.5x faster and 3x more accurate than existing tools for decoding - Tom's Hardware
- Domain: tomshardware.com
- URL: https://news.google.com/rss/articles/CBMipgFBVV95cUxPSFllNFUyaGdBXzkwZVFDMGh1anU0Qmw0dlNvMUJyd2lVaTRfRFFtZlAxU21MYjRneFhvNUhrV3BaYWstN0NOZmJfM255c3BRNVJjNG5Jd3dfcmhGd3JPRGpWWEY0NVRNeHAxTjVHWGhxc0FkSU9fN2JpTXlFT1dUdzFablVzVjRxQ1pkcjZYc0pMVS11WGFyVkQ2aFVvTEppaXV1Tkl3
- Relevance score: 5.5
- Published: Wed, 15 Apr 2026 09:00:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMipgFBVV95cUxPSFllNFUyaGdBXzkwZVFDMGh1anU0Qmw0dlNvMUJyd2lVaTRfRFFtZlAxU21MYjRneFhvNUhrV3BaYWstN0NOZmJfM255c3BRNVJjNG5Jd3dfcmhGd3JPRGpWWEY0NVRNeHAxTjVHWGhxc0FkSU9fN2JpTXlFT1dUdzFablVzVjRxQ1pkcjZYc0pMVS11WGFyVkQ2aFVvTEppaXV1Tkl3?oc=5" target="_blank">Nvidia releases open AI models for quantum computing tasks — 'Ising' said to be 2.5x faster and 3x more accurate than existing tools for decoding</a>&nbsp;&nbsp;<font color="#6f6f6f">Tom's Hardware</font>

## 13. Former Blinkit executives’ AI startup raises Rs 140 crore to expand globally - Indian Startup News
- Domain: indianstartupnews.com
- URL: https://news.google.com/rss/articles/CBMivwFBVV95cUxQbk5mQWZ0TXhZNXU3MUExek44cEFIWktBakFOa1MyQ2UzM19kR0hSNTdsN1BlT21CUmZpYlFkZmMzVWpLUWRNdGNGOWpYVFN1dUMzYndSNkgydHhpSnhtSUQtbnEwNXd6RENsYngxQVF4alBIX1QwRThmRjRuWXVwUllkN1FSdE9tamNvU3RKaGJCcnI5VDVUQzJ5bjVqZk5jbGJfTEpvTjNJWFZkOUhqUklTZG9uMFpUaDctWmtVUdIBvwFBVV95cUxQbk5mQWZ0TXhZNXU3MUExek44cEFIWktBakFOa1MyQ2UzM19kR0hSNTdsN1BlT21CUmZpYlFkZmMzVWpLUWRNdGNGOWpYVFN1dUMzYndSNkgydHhpSnhtSUQtbnEwNXd6RENsYngxQVF4alBIX1QwRThmRjRuWXVwUllkN1FSdE9tamNvU3RKaGJCcnI5VDVUQzJ5bjVqZk5jbGJfTEpvTjNJWFZkOUhqUklTZG9uMFpUaDctWmtVUQ
- Relevance score: 5.0
- Published: Wed, 15 Apr 2026 08:56:23 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMivwFBVV95cUxQbk5mQWZ0TXhZNXU3MUExek44cEFIWktBakFOa1MyQ2UzM19kR0hSNTdsN1BlT21CUmZpYlFkZmMzVWpLUWRNdGNGOWpYVFN1dUMzYndSNkgydHhpSnhtSUQtbnEwNXd6RENsYngxQVF4alBIX1QwRThmRjRuWXVwUllkN1FSdE9tamNvU3RKaGJCcnI5VDVUQzJ5bjVqZk5jbGJfTEpvTjNJWFZkOUhqUklTZG9uMFpUaDctWmtVUdIBvwFBVV95cUxQbk5mQWZ0TXhZNXU3MUExek44cEFIWktBakFOa1MyQ2UzM19kR0hSNTdsN1BlT21CUmZpYlFkZmMzVWpLUWRNdGNGOWpYVFN1dUMzYndSNkgydHhpSnhtSUQtbnEwNXd6RENsYngxQVF4alBIX1QwRThmRjRuWXVwUllkN1FSdE9tamNvU3RKaGJCcnI5VDVUQzJ5bjVqZk5jbGJfTEpvTjNJWFZkOUhqUklTZG9uMFpUaDctWmtVUQ?oc=5" target="_blank">Former Blinkit executives’ AI startup raises Rs 140 crore to expand globally</a>&nbsp;&nbsp;<font color="#6f6f6f">Indian Startup News</font>

## 14. ‘There is no silver bullet’: How 2 colleges use AI to support nontraditional learners - Higher Ed Dive
- Domain: highereddive.com
- URL: https://news.google.com/rss/articles/CBMitAFBVV95cUxQV3lpMkFxV0NWU3lDWDFoSElsdHU5SlE0dVJnODgxNHAtTlpycko1OElqVk5MZHdGbS1qRF9wOC10YnVQTnhpSGM0TXQ0Z1ZPQVFKREdJWTBFdmREcElfMDYxSUZjdzYwZHRvOThjM3R0aHVQMm9kZnhCeGRWZ21Id0RONzdfdkxOY1FPX2J5SkVBcDdOSUVlUngzV0taWlQ4WVBIVXlWdVN6T3h0VTE3b0ZWcks
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:07:32 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMitAFBVV95cUxQV3lpMkFxV0NWU3lDWDFoSElsdHU5SlE0dVJnODgxNHAtTlpycko1OElqVk5MZHdGbS1qRF9wOC10YnVQTnhpSGM0TXQ0Z1ZPQVFKREdJWTBFdmREcElfMDYxSUZjdzYwZHRvOThjM3R0aHVQMm9kZnhCeGRWZ21Id0RONzdfdkxOY1FPX2J5SkVBcDdOSUVlUngzV0taWlQ4WVBIVXlWdVN6T3h0VTE3b0ZWcks?oc=5" target="_blank">‘There is no silver bullet’: How 2 colleges use AI to support nontraditional learners</a>&nbsp;&nbsp;<font color="#6f6f6f">Higher Ed Dive</font>

## 15. Replace staff with AI before it gets too expensive - cio.com
- Domain: cio.com
- URL: https://news.google.com/rss/articles/CBMinAFBVV95cUxOeFlRQm9WU25hVkxSUk9UTDI1Z1p0NFkwdGJ4TWR3TUFhT3FXdDczSXdXTnhyZHMzd3NyeTk0V2lSY0FxNlBVNDFYZXVvemdqUnRnSDlrbHNZRm85ZDlxeU5Ib2lNcXNJUUNxQ2k0WEl2a3BNM1JZQU9RSjdhRTFvVlR6VjFReEJnRVc0TDlMMnRGYWVGZnF0UzJmdXE
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:04:59 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMinAFBVV95cUxOeFlRQm9WU25hVkxSUk9UTDI1Z1p0NFkwdGJ4TWR3TUFhT3FXdDczSXdXTnhyZHMzd3NyeTk0V2lSY0FxNlBVNDFYZXVvemdqUnRnSDlrbHNZRm85ZDlxeU5Ib2lNcXNJUUNxQ2k0WEl2a3BNM1JZQU9RSjdhRTFvVlR6VjFReEJnRVc0TDlMMnRGYWVGZnF0UzJmdXE?oc=5" target="_blank">Replace staff with AI before it gets too expensive</a>&nbsp;&nbsp;<font color="#6f6f6f">cio.com</font>

## 16. How future CIOs may assess this period in AI history - cio.com
- Domain: cio.com
- URL: https://news.google.com/rss/articles/CBMimAFBVV95cUxPN3NBMVJNQUdBVWdGZWp4UDBhQmkwMm00QnVnbmx6aEFkbXdNckFvcDJ0XzJrdi13SUQxTWdiN24zbTdfRHVLSXJHbmEybmlCbzJNaVJQYklmWEZQRUxsNkdBNUFQbFBFaDV4QUszQ1AzbWNuSm9PbXV1MW8yYW9ROFFPT0RrREV1VzNIWjNONzJSRG10VnlwOA
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:03:40 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxPN3NBMVJNQUdBVWdGZWp4UDBhQmkwMm00QnVnbmx6aEFkbXdNckFvcDJ0XzJrdi13SUQxTWdiN24zbTdfRHVLSXJHbmEybmlCbzJNaVJQYklmWEZQRUxsNkdBNUFQbFBFaDV4QUszQ1AzbWNuSm9PbXV1MW8yYW9ROFFPT0RrREV1VzNIWjNONzJSRG10VnlwOA?oc=5" target="_blank">How future CIOs may assess this period in AI history</a>&nbsp;&nbsp;<font color="#6f6f6f">cio.com</font>
