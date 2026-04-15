# Source manifest — 2026-04-15

Generated at: 2026-04-15T11:22:25.107202+00:00
Profile: daily
Relevant source count: 21

## 1. China’s Dishan Technology nears 2nm AI chip breakthrough, reports say
- Domain: scmp.com
- URL: https://www.scmp.com/tech/tech-trends/article/3350050/chinas-dishan-technology-nears-2nm-ai-chip-breakthrough-reports-say
- Relevance score: 14.0
- Published: Tue, 14 Apr 2026 10:59:56 +0000
- Summary: Chinese chip start-up Dishan Technology has achieved a breakthrough in designing a 2-nanometre artificial intelligence chip, according to local media reports. Shanghai-based Dishan, which focuses on the development of high-performance computing chips and sensor chips, was now in the crucial prototype verification stage for its first 2nm AI graphics processing unit (GPU), the Shanghai Morning Post reported recently. The GPU was unveiled by the company last July. The company then said it had...
- Extract: Edition: International [](https://www.scmp.com/mynews) [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/?module=masthead&pgtype=article) [](https://www.scmp.com/search?module=masthead&pgtype=article) [Tech Trends](https://www.scmp.com/tech/tech-trends) - All [Tech Trends](https://www.scmp.com/tech/tech-trends) China’s Dishan Technology nears 2nm AI chip breakthrough, reports say [](https://www.scmp.com/?module=masthead&pgtype=article) SIGN IN Advertisement [Semiconductors](https://www.scmp.com/topics/semiconductors?module=breadcrumb&pgtype=article) [Tech](https://www.scmp.com/tech?module=breadcrumb&pgtype=article)[Tech Trends](https://www.scmp.com/tech/tech-trends?module=breadcrumb&pgtype=article) # China’s Dishan Technology nears 2nm AI chip breakthrough, r

## 2. GRACE: A Dynamic Coreset Selection Framework for Large Language Model Optimization
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.11810
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.11810v1 Announce Type: cross Abstract: Large Language Models (LLMs) have demonstrated remarkable capabilities in natural language understanding and generation. However, their immense number of parameters and complex transformer-based architectures result in significant resource demands and computational complexity during training, making it challenging to optimize them efficiently on large datasets. To reduce training costs while preserving performance, researchers have investigated coreset selection techniques, which aim to identify small, representative subsets of the entire training dataset to accelerate LLM training. However, existing coreset selection methods fail to adapt to the dynamic nature of LLM training and often struggle with scalability for models of this size. To address these limitations, we propose a graph-guided adaptive and dynamic coreset selection framework for LLMs, namely GRACE. GRACE dynamically constructs and updates coresets by combining representation diversity with gradient-based importance metrics, ensuring both informativeness and efficiency. To mitigate the computational cost of frequent updates, GRACE leverages a $k$-NN graph-based propaga

## 3. SEA-Eval: A Benchmark for Evaluating Self-Evolving Agents Beyond Episodic Assessment
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.08988
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.08988v2 Announce Type: replace Abstract: Current LLM-based agents demonstrate strong performance in episodic task execution but remain constrained by static toolsets and episodic amnesia, failing to accumulate experience across task boundaries. This paper presents the first formal definition of the Self-Evolving Agent (SEA), formalizes the Evolutionary Flywheel as its minimal sufficient architecture, and introduces SEA-Eval -- the first benchmark designed specifically for evaluating SEAs. Grounded in Flywheel theory, SEA-Eval establishes $SR$ and $T$ as primary metrics and enables through sequential task stream design the independent quantification of evolutionary gain, evolutionary stability, and implicit alignment convergence. Empirical evaluation reveals that under identical success rates, token consumption differs by up to 31.2$\times$ across frameworks, with divergent evolutionary trajectories under sequential analysis -- demonstrating that success rate alone creates a capability illusion and that the sequential convergence of $T$ is the key criterion for distinguishing genuine evolution from pseudo-evolution.

## 4. MeloTune: On-Device Arousal Learning and Peer-to-Peer Mood Coupling for Proactive Music Curation
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.10815
- Relevance score: 13.5
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.10815v2 Announce Type: replace-cross Abstract: MeloTune is an iPhone-deployed music agent that instantiates the Mesh Memory Protocol (MMP) and Symbolic-Vector Attention Fusion (SVAF) as a production system for affect-aware music curation with peer-to-peer mood coupling. Each device runs two closed-form continuous-time (CfC) networks: a private listener-level CfC that predicts a short-horizon affective trajectory on Russell's circumplex and drives proactive curation, and a shared mesh-runtime CfC at MMP Layer 6 that integrates Cognitive Memory Blocks (CMBs) from co-listening peers. CfC hidden states never cross the wire; only structured CMBs do. A Personal Arousal Function (PAF) replaces the standard linear mapping from audio intensity to psychological arousal with a per-listener learned adjustment, trained from behavioral signals (skip, completion, favorite, volume) and from drift between user-declared mood and machine inference. The same track receives different arousal predictions for different listeners. The model (94,552 parameters) achieves trajectory MAE 0.414, pattern accuracy 96.6%, and intent accuracy 69.4% on held-out validation. PAF evidence from a live deploy

## 5. SpecBound: Adaptive Bounded Self-Speculation with Layer-wise Confidence Calibration
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12247
- Relevance score: 13.0
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12247v1 Announce Type: new Abstract: Speculative decoding has emerged as a promising approach to accelerate autoregressive inference in large language models (LLMs). Self-draft methods, which leverage the base LLM itself for speculation, avoid the overhead of auxiliary draft models but face limitations: shallow layers often produce overconfident yet incorrect token predictions, and the presence of difficult tokens in a draft sequence forces redundant computation through deeper layers, undermining both draft acceptance and overall speedup. To address these issues, we propose a novel self-draft framework that suppresses spurious confidence via layer-wise temperature annealing in early-exit decision and adaptively bounds speculation length based on token-wise decoding difficulty. By reprocessing the hidden states of draft tokens in a unified parallel pass through deep layers, our method maintains exact output equivalence with the original model while maximizing computational efficiency. It requires no modifications to the base LLM parameters and achieves up to 2.33x wall-time speedup over standard autoregressive decoding across diverse long-form generation tasks and multipl

## 6. ToxiTrace: Gradient-Aligned Training for Explainable Chinese Toxicity Detection
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12321
- Relevance score: 13.0
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12321v1 Announce Type: new Abstract: Existing Chinese toxic content detection methods mainly target sentence-level classification but often fail to provide readable and contiguous toxic evidence spans. We propose \textbf{ToxiTrace}, an explainability-oriented method for BERT-style encoders with three components: (1) \textbf{CuSA}, which refines encoder-derived saliency cues into fine-grained toxic spans with lightweight LLM guidance; (2) \textbf{GCLoss}, a gradient-constrained objective that concentrates token-level saliency on toxic evidence while suppressing irrelevant activations; and (3) \textbf{ARCL}, which constructs sample-specific contrastive reasoning pairs to sharpen the semantic boundary between toxic and non-toxic content. Experiments show that ToxiTrace improves classification accuracy and toxic span extraction while preserving efficient encoder-based inference and producing more coherent, human-readable explanations. We have released the model at https://huggingface.co/ArdLi/ToxiTrace.

## 7. Decoding by Perturbation: Mitigating MLLM Hallucinations via Dynamic Textual Perturbation
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12424
- Relevance score: 13.0
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12424v1 Announce Type: new Abstract: Multimodal Large Language Models frequently suffer from inference hallucinations, partially stemming from language priors dominating visual evidence. Existing training-free mitigation methods either perturb the visual representation and deviate from the natural image distribution, or enforce intrusive manipulations that compromise the model's inherent generative fluency. We introduce a novel perspective that multimodal hallucination manifests as the hypersensitivity of visual grounding to textual phrasing during the decoding phase. Building on this insight, we propose Decoding by Perturbation (DeP), a training-free framework mitigating prior-induced hallucinations via controlled textual interventions. DeP employs a dynamic probe applying multi-level textual perturbations to elicit latent language priors. Leveraging attention variance, it enhances stable evidence regions while suppressing suspicious noise in the feature space. Furthermore, it constructs an interpretable prior drift direction using logits statistics to counteract probability biases from textual co-occurrences. Extensive experiments confirm DeP effectively reduces halluc

## 8. Learning Chain Of Thoughts Prompts for Predicting Entities, Relations, and even Literals on Knowledge Graphs
- Domain: arxiv.org
- URL: https://arxiv.org/abs/2604.12651
- Relevance score: 13.0
- Published: Wed, 15 Apr 2026 00:00:00 -0400
- Summary: arXiv:2604.12651v1 Announce Type: new Abstract: Knowledge graph embedding (KGE) models perform well on link prediction but struggle with unseen entities, relations, and especially literals, limiting their use in dynamic, heterogeneous graphs. In contrast, pretrained large language models (LLMs) generalize effectively through prompting. We reformulate link prediction as a prompt learning problem and introduce RALP, which learns string-based chain-of-thought (CoT) prompts as scoring functions for triples. Using Bayesian Optimization through MIPRO algorithm, RALP identifies effective prompts from fewer than 30 training examples without gradient access. At inference, RALP predicts missing entities, relations or whole triples and assigns confidence scores based on the learned prompt. We evaluate on transductive, numerical, and OWL instance retrieval benchmarks. RALP improves state-of-the-art KGE models by over 5% MRR across datasets and enhances generalization via high-quality inferred triples. On OWL reasoning tasks with complex class expressions (e.g., $\exists hasChild.Female$, $\geq 5 \; hasChild.Female$), it achieves over 88% Jaccard similarity. These results highlight prompt-based

## 9. Greg Brockman predicts AI will let small teams match the output of large ones if they can afford the compute
- Domain: the-decoder.com
- URL: https://the-decoder.com/greg-brockman-predicts-ai-will-let-small-teams-match-the-output-of-large-ones-if-they-can-afford-the-compute/
- Relevance score: 11.5
- Published: Tue, 14 Apr 2026 19:00:39 +0000
- Summary: <p><img alt="" class="attachment-full size-full wp-post-image" height="768" src="https://the-decoder.com/wp-content/uploads/2026/04/openai_logo_dark_blue.png" style="height: auto; margin-bottom: 10px;" width="1376" /></p> <p> In the future, working with AI won't mean adapting to the computer—the computer will adapt to you, says OpenAI President Greg Brockman. "This is disruptive. Institutions will change."</p> <p>The article <a href="https://the-decoder.com/greg-brockman-predicts-ai-will-let-small-teams-match-the-output-of-large-ones-if-they-can-afford-the-compute/">Greg Brockman predicts AI will let small teams match the output of large ones if they can afford the compute</a> appeared first on <a href="https://the-decoder.com">The Decoder</a>.</p>
- Extract: Ad [Skip to content](https://the-decoder.com/greg-brockman-predicts-ai-will-let-small-teams-match-the-output-of-large-ones-if-they-can-afford-the-compute/#content) [ ](https://the-decoder.com/) [ Log In ](https://the-decoder.com/sign-in/) [ ](https://the-decoder.com/subscription/) [DESwitch to German](https://the-decoder.de/?p=54618) Primary Menu [ ](https://the-decoder.com/) [ Log In ](https://the-decoder.com/sign-in/) [ ](https://the-decoder.com/subscription/) [DESwitch to German](https://the-decoder.de/?p=54618) Primary Menu * [ Sign In ](https://the-decoder.com/sign-in/) * [ Register ](https://the-decoder.com/register/) [ Subscribe Now ](https://the-decoder.com/subscription/) ### The Decoder [Opens discord in a new tab](https://discord.gg/8VKkHAacn8) [Opens LinkedIn in a new tab](https

## 10. Lavery is accelerating its integration of artificial intelligence into its practices and asserting its position as a leader in innovation - Yahoo! Finance Canada
- Domain: ca.finance.yahoo.com
- URL: https://news.google.com/rss/articles/CBMipwFBVV95cUxQMkFVWVl4RHVQbHFOUXZFX1R5UGY5RFFreUliazl1Zm1iTmFTRkZzbWFmaHBJOTRjRFFIOUlYbGxOM0w3Qi1laGlkS2xxOGwzeVZ6RFJ3RDV1QVItTVNiYm9ORVdkUWtWeUIxY1YybC1lVHFHSlFLWHVEYy1rTkFmcmlOcWR5ZkR4c0J6M2ppdjhsMDBram5Jc2EtS0hzVDVDb3pLVzVoZw
- Relevance score: 6.0
- Published: Wed, 15 Apr 2026 10:00:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMipwFBVV95cUxQMkFVWVl4RHVQbHFOUXZFX1R5UGY5RFFreUliazl1Zm1iTmFTRkZzbWFmaHBJOTRjRFFIOUlYbGxOM0w3Qi1laGlkS2xxOGwzeVZ6RFJ3RDV1QVItTVNiYm9ORVdkUWtWeUIxY1YybC1lVHFHSlFLWHVEYy1rTkFmcmlOcWR5ZkR4c0J6M2ppdjhsMDBram5Jc2EtS0hzVDVDb3pLVzVoZw?oc=5" target="_blank">Lavery is accelerating its integration of artificial intelligence into its practices and asserting its position as a leader in innovation</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo! Finance Canada</font>

## 11. Debate: Artificial Intelligence - KSFR
- Domain: ksfr.org
- URL: https://news.google.com/rss/articles/CBMijwFBVV95cUxQT2RqbWN4bWkzanlJV2MxU0J3UmNMd094Qzg0RHllYmQ2Q2F6ZXdkQlBVQ081djk5cE1LcFRDSTdZdEhzeFU0b3NuMFNaQ1VWbEhYR1lUZ3RMTXh6ZjNVT3VMNFAzVS1xc1VRTUlWZnRhX3VSbXdxbG90UFlRTTJWSDVrZnBOODdPYllCbE1Xcw
- Relevance score: 6.0
- Published: Tue, 14 Apr 2026 23:05:41 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMijwFBVV95cUxQT2RqbWN4bWkzanlJV2MxU0J3UmNMd094Qzg0RHllYmQ2Q2F6ZXdkQlBVQ081djk5cE1LcFRDSTdZdEhzeFU0b3NuMFNaQ1VWbEhYR1lUZ3RMTXh6ZjNVT3VMNFAzVS1xc1VRTUlWZnRhX3VSbXdxbG90UFlRTTJWSDVrZnBOODdPYllCbE1Xcw?oc=5" target="_blank">Debate: Artificial Intelligence</a>&nbsp;&nbsp;<font color="#6f6f6f">KSFR</font>

## 12. The 15 Colleges Best Preparing Students for the AI Economy - Town & Country Magazine
- Domain: townandcountrymag.com
- URL: https://news.google.com/rss/articles/CBMinAFBVV95cUxOTWsyaEJTOGFUMjlWOW1RWXlxY0V5QU05cmhtNTNCVEEtdmFYbWo5cTc3SUUtU2VLa3NvRnJYZVNiZ0xRaU5NWmxFcjlaYmZVRmJ3NmV2YUV6Qm9OWkgwVDQtZkRCeWdMWDdfSFRNUDdnUEpqWHkzTV9xNWpVLW0zbUxhdV9wOXRGaTFOMUFsQkI5WnpaYUdyVloxb3U
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 11:03:40 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMinAFBVV95cUxOTWsyaEJTOGFUMjlWOW1RWXlxY0V5QU05cmhtNTNCVEEtdmFYbWo5cTc3SUUtU2VLa3NvRnJYZVNiZ0xRaU5NWmxFcjlaYmZVRmJ3NmV2YUV6Qm9OWkgwVDQtZkRCeWdMWDdfSFRNUDdnUEpqWHkzTV9xNWpVLW0zbUxhdV9wOXRGaTFOMUFsQkI5WnpaYUdyVloxb3U?oc=5" target="_blank">The 15 Colleges Best Preparing Students for the AI Economy</a>&nbsp;&nbsp;<font color="#6f6f6f">Town & Country Magazine</font>

## 13. AI ruling prompts warnings from US lawyers: Your chats could be used against you - Reuters
- Domain: reuters.com
- URL: https://news.google.com/rss/articles/CBMixgFBVV95cUxPR2ZtWkI5VERwRTZkZDVXU3VuVUxiY2N6N3FfYlNpNUZ6OFViQVhvTmwtYVpTb1VjM1NCWWVfM2Q2dkI3YzdZb3NyTkR0VG5TNXNveWlQTGlrYWlqYmEwTWYxVk12TkRQbTlxYTlLaXJZbzU2UkFwVjZsSnlnT1RWVm5MdDU4RW56Rnc1cEZybnR4anQ0dGsyNTdwV0Vpay1TajV4d2RPZ0ZldzdfRmRMdHRoOFgtVVJfVFU2SnNteHdmSFVnZWc
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 10:57:03 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMixgFBVV95cUxPR2ZtWkI5VERwRTZkZDVXU3VuVUxiY2N6N3FfYlNpNUZ6OFViQVhvTmwtYVpTb1VjM1NCWWVfM2Q2dkI3YzdZb3NyTkR0VG5TNXNveWlQTGlrYWlqYmEwTWYxVk12TkRQbTlxYTlLaXJZbzU2UkFwVjZsSnlnT1RWVm5MdDU4RW56Rnc1cEZybnR4anQ0dGsyNTdwV0Vpay1TajV4d2RPZ0ZldzdfRmRMdHRoOFgtVVJfVFU2SnNteHdmSFVnZWc?oc=5" target="_blank">AI ruling prompts warnings from US lawyers: Your chats could be used against you</a>&nbsp;&nbsp;<font color="#6f6f6f">Reuters</font>

## 14. The good, the bad and the unknown: The future of AI in North Carolina - NC Newsline
- Domain: ncnewsline.com
- URL: https://news.google.com/rss/articles/CBMipAFBVV95cUxPVEtjZlZXV0ZLWi1xWWxIOENLUE4ydmExVWdWTHlhZ3RsSm9TQUxfbHZMLVd6WmVJQ3NGYU9HYlA1eUREbWEtZDBtMEdkeklqS0hzWnUtNm91WmVCTFBMS3RGaXpZNndITzlWa2FZcEtRQ09HY0VwaU5OMEQxZ2RwVzhIWUxqZUFfZE5uamVVeEdMR21ZZjlsQTUwdWZ5M3RHaXZLNQ
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 10:03:30 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMipAFBVV95cUxPVEtjZlZXV0ZLWi1xWWxIOENLUE4ydmExVWdWTHlhZ3RsSm9TQUxfbHZMLVd6WmVJQ3NGYU9HYlA1eUREbWEtZDBtMEdkeklqS0hzWnUtNm91WmVCTFBMS3RGaXpZNndITzlWa2FZcEtRQ09HY0VwaU5OMEQxZ2RwVzhIWUxqZUFfZE5uamVVeEdMR21ZZjlsQTUwdWZ5M3RHaXZLNQ?oc=5" target="_blank">The good, the bad and the unknown: The future of AI in North Carolina</a>&nbsp;&nbsp;<font color="#6f6f6f">NC Newsline</font>

## 15. The US-China AI gap closed. The responsible AI gap didn’t - AI News
- Domain: artificialintelligence-news.com
- URL: https://news.google.com/rss/articles/CBMimwFBVV95cUxOV3E4M2xuclZCdmxUQnc3aUlrUnI1NV82NWR5VEtZMDVyMEpSaE5KZkozX3ZER3NUWEl1UFFoVTVldk8zcWw3SFZmZkV6OUFkSjdzUWRmY2tQQXJpWThISXVfalpEaERtMXRvcGFYNjdXM2pwQXJIdGFmMGMzOV91QVFaSUN5SkI0YUNpd0g5Q2dnNlVvYmpLYmdyaw
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 10:00:36 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMimwFBVV95cUxOV3E4M2xuclZCdmxUQnc3aUlrUnI1NV82NWR5VEtZMDVyMEpSaE5KZkozX3ZER3NUWEl1UFFoVTVldk8zcWw3SFZmZkV6OUFkSjdzUWRmY2tQQXJpWThISXVfalpEaERtMXRvcGFYNjdXM2pwQXJIdGFmMGMzOV91QVFaSUN5SkI0YUNpd0g5Q2dnNlVvYmpLYmdyaw?oc=5" target="_blank">The US-China AI gap closed. The responsible AI gap didn’t</a>&nbsp;&nbsp;<font color="#6f6f6f">AI News</font>

## 16. Consulting Was a Dream First Job Until AI Destroyed Those Roles - Bloomberg Law News
- Domain: news.bloomberglaw.com
- URL: https://news.google.com/rss/articles/CBMiuAFBVV95cUxOeURyMG1TRzlZY0c3MmgwRDhoTEVxN0d4bndlV2JXUmd0U1JDOUdVRFZyQU1iRGdMRlRPcm5faHBSSWNsaFZ2MWdWYmFJOXpJdFRJVlVKckVYU3hZQnFyb1NmZkRWSGNtQlBUZHBlTmpCcGNWUktLQmRJeF9LU0JRRGJxcnpSajhNazdQZWFnOGY4WDM1NlRvQldxRG0zWHNfZnBrQ2F0bl9td3BHQkdjbjhVS2k2VWUt
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 10:00:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMiuAFBVV95cUxOeURyMG1TRzlZY0c3MmgwRDhoTEVxN0d4bndlV2JXUmd0U1JDOUdVRFZyQU1iRGdMRlRPcm5faHBSSWNsaFZ2MWdWYmFJOXpJdFRJVlVKckVYU3hZQnFyb1NmZkRWSGNtQlBUZHBlTmpCcGNWUktLQmRJeF9LU0JRRGJxcnpSajhNazdQZWFnOGY4WDM1NlRvQldxRG0zWHNfZnBrQ2F0bl9td3BHQkdjbjhVS2k2VWUt?oc=5" target="_blank">Consulting Was a Dream First Job Until AI Destroyed Those Roles</a>&nbsp;&nbsp;<font color="#6f6f6f">Bloomberg Law News</font>

## 17. Scientists turn AI-generated proteins into smart molecular sensors - EurekAlert!
- Domain: eurekalert.org
- URL: https://news.google.com/rss/articles/CBMiXEFVX3lxTE9PU2hNUnVISkhSV2dybDNocEMtbGt2QXFTbHdySTYtRmtoV3djYVZiTjJtSGpKc0pDeGV6eXFPbElXZkEzR3ItX24xcXlwX1pCSlo2Y0hodDBCNzUt
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:38:25 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMiXEFVX3lxTE9PU2hNUnVISkhSV2dybDNocEMtbGt2QXFTbHdySTYtRmtoV3djYVZiTjJtSGpKc0pDeGV6eXFPbElXZkEzR3ItX24xcXlwX1pCSlo2Y0hodDBCNzUt?oc=5" target="_blank">Scientists turn AI-generated proteins into smart molecular sensors</a>&nbsp;&nbsp;<font color="#6f6f6f">EurekAlert!</font>

## 18. What AI means for the future of WWSP's World's Largest Trivia Contest - Wausau Daily Herald
- Domain: wausaudailyherald.com
- URL: https://news.google.com/rss/articles/CBMi-wFBVV95cUxQdWJOemkwNUZxVkpTbE9fMmJXc0IwRmtSLTFlQzEzdlROSlJlZ084RjlGU2c4eVM5SkVSVHlVRlpIR0xyME1ndkFyQnU1dHlkZGVtVkstMF9fd3NTR29abWdNTmNFZzRhcVZTV3VuTVZQeFN1QWNMMXFacFVwYmdpWmpfUXlVeXFlamxROHJkOVljQU1XbW5XTGVFU0w5ZjU4cGFyNjI0YjZlSXgtMk9rUFBpSWFxelRxLW5yMUlsZ2Q0c1FLWEI0NmVtbUpHU25DNG1CN3NhcVZmY05nenhSUllEQVlwMUhlV3c0LTJhSjIxblZKN1BwekVpNA
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:12:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMi-wFBVV95cUxQdWJOemkwNUZxVkpTbE9fMmJXc0IwRmtSLTFlQzEzdlROSlJlZ084RjlGU2c4eVM5SkVSVHlVRlpIR0xyME1ndkFyQnU1dHlkZGVtVkstMF9fd3NTR29abWdNTmNFZzRhcVZTV3VuTVZQeFN1QWNMMXFacFVwYmdpWmpfUXlVeXFlamxROHJkOVljQU1XbW5XTGVFU0w5ZjU4cGFyNjI0YjZlSXgtMk9rUFBpSWFxelRxLW5yMUlsZ2Q0c1FLWEI0NmVtbUpHU25DNG1CN3NhcVZmY05nenhSUllEQVlwMUhlV3c0LTJhSjIxblZKN1BwekVpNA?oc=5" target="_blank">What AI means for the future of WWSP's World's Largest Trivia Contest</a>&nbsp;&nbsp;<font color="#6f6f6f">Wausau Daily Herald</font>

## 19. NC Treasurer’s office expands use of AI throughout the agency - The Asheville Citizen Times
- Domain: citizen-times.com
- URL: https://news.google.com/rss/articles/CBMiwwFBVV95cUxNeFIxcWp1YXgzWUhfLXc1WWpXSEpHUVN6VnpjajNvSGF4UU9Qc0wwT1VYN1NNUVFlWmIzZjFEeFhHeDNuZmF4T3dtU2xwWXZ4RE5La2NWZUZJQi1DNmduWkd5cU5nbjdzWVFzT0RpVjhibVRIanhWb3NRZ3lOUTdPYmthTjBQY090MjJPVHNpMklfV0l0c25LNGp0NnAyLUtYZGtja3dOUFVvTFpQTVVFOUhoVURzb1V6N0sySXYtQW5lSTg
- Relevance score: 4.5
- Published: Wed, 15 Apr 2026 09:04:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMiwwFBVV95cUxNeFIxcWp1YXgzWUhfLXc1WWpXSEpHUVN6VnpjajNvSGF4UU9Qc0wwT1VYN1NNUVFlWmIzZjFEeFhHeDNuZmF4T3dtU2xwWXZ4RE5La2NWZUZJQi1DNmduWkd5cU5nbjdzWVFzT0RpVjhibVRIanhWb3NRZ3lOUTdPYmthTjBQY090MjJPVHNpMklfV0l0c25LNGp0NnAyLUtYZGtja3dOUFVvTFpQTVVFOUhoVURzb1V6N0sySXYtQW5lSTg?oc=5" target="_blank">NC Treasurer’s office expands use of AI throughout the agency</a>&nbsp;&nbsp;<font color="#6f6f6f">The Asheville Citizen Times</font>

## 20. SwRI harnesses AI to find meaningful matches in solar data - EurekAlert!
- Domain: eurekalert.org
- URL: https://news.google.com/rss/articles/CBMiXEFVX3lxTE1GOEVteGVKSm5DemNYaHlBWkZQRnNZMjY2Nkt0dlI5ckg1VGFEdmtkeE9NNGRPVlVwenA5TFNpc0ttTGxkUmU5ZkpWazE4WVhPWnRLN0pOYTF0TGVT
- Relevance score: 4.5
- Published: Tue, 14 Apr 2026 19:52:28 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMiXEFVX3lxTE1GOEVteGVKSm5DemNYaHlBWkZQRnNZMjY2Nkt0dlI5ckg1VGFEdmtkeE9NNGRPVlVwenA5TFNpc0ttTGxkUmU5ZkpWazE4WVhPWnRLN0pOYTF0TGVT?oc=5" target="_blank">SwRI harnesses AI to find meaningful matches in solar data</a>&nbsp;&nbsp;<font color="#6f6f6f">EurekAlert!</font>

## 21. Attempted fire-bombing has tech titans worried about AI backlash - The Washington Post
- Domain: washingtonpost.com
- URL: https://news.google.com/rss/articles/CBMijAFBVV95cUxNZWRIN2VsMjVTTF9QSHltdFRCbktNcG1FM2ZsWEZYYkQ3QzR0N3g1TENJLWk5WFdmWmtDcnZGZ3hYajFfOEdGVjJFU3E4WEJwQVAxSnlpTExhT3pOUG5sZlQ3b09GcURuYklfT0NDUjQ5NVRHX2xtUVZ2VnJPUkVTdDRuZHMza0RIWWRDWQ
- Relevance score: 4.5
- Published: Tue, 14 Apr 2026 16:00:00 GMT
- Summary: <a href="https://news.google.com/rss/articles/CBMijAFBVV95cUxNZWRIN2VsMjVTTF9QSHltdFRCbktNcG1FM2ZsWEZYYkQ3QzR0N3g1TENJLWk5WFdmWmtDcnZGZ3hYajFfOEdGVjJFU3E4WEJwQVAxSnlpTExhT3pOUG5sZlQ3b09GcURuYklfT0NDUjQ5NVRHX2xtUVZ2VnJPUkVTdDRuZHMza0RIWWRDWQ?oc=5" target="_blank">Attempted fire-bombing has tech titans worried about AI backlash</a>&nbsp;&nbsp;<font color="#6f6f6f">The Washington Post</font>
