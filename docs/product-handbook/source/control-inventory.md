# Forms actions sections and conditional controls

Source-only inventory. Labels containing interpolation vary at runtime. No action was executed. Full bindings and handlers are in ui-inventory.json for maintenance review.

## P001 apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts

Routes: /intelligence/sourcing-economics

Headings: Review sourcing economics; Product and supplier for this evaluation; Your sourcing evaluation at a glance; Approve, authorize, then review one source; Scoped approvals; Execution authorizations; Certification history; Decision brief; {{ brief.product.name }}; Review and control supplier contact; {{ draft.subject }}; Review supplier responses; {{ response.classification.replaceAll('_', ' ') }}; No inbound supplier responses; Evidence-backed commercial reassessment; Quote v{{ item.quote_version }} · {{ item.status }}; Compare supplier scenarios; Supplier comparison review; Comparison v{{ snapshot.snapshot_version }}; {{ supplier.supplier }}; Comparable metrics and differences; Supplier due diligence and procurement readiness; {{ procurementSupplierName(assessment) }} · assessment v{{ assessment.snapshot_version }}; {{ entry[0].replaceAll('_', ' ') }}; Reassess from reviewed supplier evidence; Decision readiness; Blocking evidence; Warnings; Unknowns; Explainable decision synthesis; What supports this state; What prevents stronger progression; Warnings and unknowns; Next safe actions; Controlled recommendation and your decision; Evidence supporting progression; Evidence against progression or still unresolved; Limitations; Your decision; {{ brief.economics.unit_economics?.freshness?.recalculation_required ? 'Historical landed-cost evidence - recalculate before use' : 'Known landed-cost evidence' }}; Explainable landed-cost breakdown; Modeled unit economics and capital fit; Included selling-cost components; Unknown or excluded costs; Limitations; Scenario comparison (no automatic winner); What still needs review; Sourcing context; Inputs and provenance; {{ calculation()?.explanation?.included_total_label }}; Cost breakdown and lineage; Missing / excluded inputs; Warnings; Bounded what-if scenario; Comparison result; Bounded sensitivity points

Disclosures: Optional: live supplier source certification; Gate outcomes and provenance; Advanced decision identifiers; Inspect draft message, warnings, unknowns, and limitations; SUPPLIER SAID — inspect immutable raw response; VAYUJIT DERIVED — inspect extraction v{{ extraction.version }} and provenance; Review decision readiness, warnings and unknowns; Review explainable decision synthesis; Exact component values; Exact canonical decimal values (unrounded); Exact selling-cost values

Dialogs: 0; tables: 4.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| {{ context() ? 'Review saved economic inputs' : 'Set up economic inputs' }} | a | Not statically bound |
| Review product opportunities | a | Not statically bound |
| Choose a product opportunity | a | Not statically bound |
| Review inputs | a | Not statically bound |
| Review cost model | a | Not statically bound |
| Review HUMAN decision | a | Not statically bound |
| Create HUMAN approval | button | Yes; runtime evaluation unverified |
| Authorize one HUMAN read | button | Yes; runtime evaluation unverified |
| Revoke approval | button | Yes; runtime evaluation unverified |
| Execute authorized read | button | Yes; runtime evaluation unverified |
| Revoke authorization | button | Yes; runtime evaluation unverified |
| Accept evidence as HUMAN-reviewed | button | Yes; runtime evaluation unverified |
| Mark contradiction | button | Yes; runtime evaluation unverified |
| Choose a product opportunity | a | Not statically bound |
| Set up this supplier's economic inputs | a | Not statically bound |
| Load decision brief | button | Yes; runtime evaluation unverified |
| Approve for future send (no message sent) | button | Yes; runtime evaluation unverified |
| Authorize Send RFQ | button | Yes; runtime evaluation unverified |
| Send RFQ | button | Yes; runtime evaluation unverified |
| Cancel draft | button | Yes; runtime evaluation unverified |
| Accept extracted claims for promotion | button | Yes; runtime evaluation unverified |
| Correct extraction | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Reject extraction | button | Yes; runtime evaluation unverified |
| Promote accepted claims to PR-5A evidence | button | Yes; runtime evaluation unverified |
| Acknowledge and keep under review | button | Yes; runtime evaluation unverified |
| Create or refresh comparison | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Approve for sourcing (HUMAN) | button | Yes; runtime evaluation unverified |
| Exclude from shortlist | button | Yes; runtime evaluation unverified |
| Run readiness assessment for {{ supplier.supplier }} | button | Yes; runtime evaluation unverified |
| Acknowledge review | button | Yes; runtime evaluation unverified |
| Request further evidence | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Reassess reviewed supplier quote | button | Yes; runtime evaluation unverified |
| Proceed | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Do not proceed | button | Yes; runtime evaluation unverified |
| Prepare advisory assessment for review | button | Yes; runtime evaluation unverified |
| {{ action.replaceAll('_', ' ') }} | button | Yes; runtime evaluation unverified |
| Create context | button | Yes; runtime evaluation unverified |
| Freeze immutable input snapshot | button | Yes; runtime evaluation unverified |
| Calculate from snapshot | button | Yes; runtime evaluation unverified |
| Create hypothetical scenario | button | Yes; runtime evaluation unverified |
| Run comparison | button | Yes; runtime evaluation unverified |
| Run bounded sensitivity | button | Yes; runtime evaluation unverified |

## P002 apps/web/src/app/intelligence/supplier-engagement-workspace.component.ts

Routes: /intelligence/supplier-engagement

Headings: Prepare and review supplier engagement; {{ brief()?.product?.name \|\| 'Selected product opportunity' }}; Prepare a supplier information request; {{ statusLabel(engagement()!.status) }}; Review the exact RFQ draft; Separate approval from execution; Review inbound evidence; {{ response.classification.replaceAll('_', ' ') }}; Continue only after evidence review; Engagement history

Disclosures: Inspect draft message and evidence limitations; Inspect immutable supplier response

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Review economics | a | Not statically bound |
| Choose a product opportunity | a | Not statically bound |
| Open supplier verification | a | Not statically bound |
| Open supplier shortlisting | a | Not statically bound |
| Prepare internal draft | button | Yes; runtime evaluation unverified |
| Approve draft for future review | button | Yes; runtime evaluation unverified |
| Cancel internal draft | button | Yes; runtime evaluation unverified |
| Issue single-use send authorization | button | Yes; runtime evaluation unverified |
| Accept extracted claims | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Review sourcing economics and readiness | a | Not statically bound |
| Refresh history | button | Yes; runtime evaluation unverified |

## P003 apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts

Routes: /intelligence/trends, /intelligence/trends/:contextId

Headings: Trend Intelligence; Trend research context; Contexts; Trend evidence; Local fixture ingestion; Evidence observations; Observed time-series analysis; Evidence validation and confidence; Change and momentum history

Disclosures: Advanced / manual context

Dialogs: 0; tables: 3.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| {{ advancedContextOpen ? 'Hide advanced research controls' : 'Open advanced research controls' }} | button | Not statically bound |
| Create manual context | button | Not statically bound |
| {{ context.name }} - {{ context.status }} | button | Not statically bound |
| Ingest local fixture | button | Not statically bound |
| Analyze latest immutable snapshot | button | Not statically bound |
| Validate latest analysis | button | Yes; runtime evaluation unverified |
| Compare latest analyses | button | Yes; runtime evaluation unverified |

## P004 apps/web/src/app/intelligence/seller-research.component.ts

Routes: /intelligence/research

Headings: My research; No saved goals yet; {{ goal.raw_goal }}

Disclosures: Advanced research configuration

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create a research goal | a | Not statically bound |
| Retry saved research | button | Not statically bound |
| Open goal, plan and research | a | Not statically bound |
| Review this goal's opportunities | a | Not statically bound |
| Open research tools and configuration | a | Not statically bound |

## P005 apps/web/src/app/intelligence/business-agent-workspace.component.ts

Routes: /intelligence/business-agent

Headings: What are you trying to accomplish?; How goals become product decisions; {{ goals().length ? 'Tell VAYUJIT what to research next' : 'Start with a business outcome' }}; Research goals and runs; {{ goal.raw_goal }}; Research plan; Research progress; What surfaced for review; No canonical product opportunity yet; VAYUJIT is waiting for your approval; Evidence-backed outcome; Trend Intelligence; Customer-feedback evidence; Sourcing Economics; Supplier intelligence continuation; Supporting evidence; What VAYUJIT found

Disclosures: How this workspace operates; {{ goals().length ? 'Start another research goal' : 'Start with a business outcome' }}; Advanced research options; Goal assumptions and technical details; Research details - plan v{{ plan.version }}; Execution detail; Research detail; Research details and execution timeline; Previous research ({{ previousGoals().length }})

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Intelligence | a | Not statically bound |
| Product opportunities | a | Not statically bound |
| Supplier intelligence | a | Not statically bound |
| Review evidence-backed operational recommendations | a | Not statically bound |
| Review orders and inventory implications | a | Not statically bound |
| Review financial projections | a | Not statically bound |
| Open saved research | a | Not statically bound |
| Create research goal | button | Yes; runtime evaluation unverified |
| Create goal | a | Not statically bound |
| Review opportunities for this goal | a | Not statically bound |
| Prepare a revised goal | button | Not statically bound |
| Create versioned research plan | button | Yes; runtime evaluation unverified |
| Start run | button | Yes; runtime evaluation unverified |
| Compare products | a | Not statically bound |
| Open Product Opportunities | a | Not statically bound |
| Open Product Opportunities | a | Not statically bound |
| Pause run | button | Not statically bound |
| {{ run.status === 'PARTIAL' ? 'Resume failed step' : 'Resume run' }} | button | Not statically bound |
| Cancel run | button | Not statically bound |
| {{ awaitingSourceReview(run) ? 'Continue product discovery' : run.status === 'PARTIAL' ? 'Retry product discovery' : 'Retry through existing runtime' }} | button | Not statically bound |
| Refresh run | button | Not statically bound |
| Approve and complete | button | Not statically bound |
| Reject and stop | button | Not statically bound |
| Review supplier intelligence | a | Not statically bound |
| Open saved goal and research | a | Not statically bound |
| Delete | button | Yes; runtime evaluation unverified |

## P006 apps/web/src/app/intelligence/sourcing-scenarios.component.ts

Routes: /intelligence/sourcing-scenarios

Headings: Sourcing Scenarios; Start from a shortlist; Analysis contexts; Custom supplier mix; Comparison; History and report; {{ s.name }} ? version {{ s.version }}; What-if (does not change supplier evidence)

Disclosures: Allocation, cost, capital, MOQ, lead time, FX, risk, and evidence

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Supplier Shortlisting | a | Not statically bound |
| Due Diligence | a | Not statically bound |
| Create analysis context | button | Yes; runtime evaluation unverified |
| {{ c.settings.target_market }} / {{ c.settings.target_channel }} / {{ c.settings.target_quantity }} units - {{ c.status }} | button | Yes; runtime evaluation unverified |
| Open Supplier Shortlisting | a | Not statically bound |
| Remove allocation | button | Yes; runtime evaluation unverified |
| Add supplier allocation | button | Yes; runtime evaluation unverified |
| Calculate custom scenario | button | Yes; runtime evaluation unverified |
| Generate evidenced baselines | button | Yes; runtime evaluation unverified |
| {{ item.name }} ? {{ item.labels.join(', ') \|\| 'Human review required' }} | button | Not statically bound |
| Recommend for human review | button | Yes; runtime evaluation unverified |
| {{ s.name }} v{{ s.version }} | button | Not statically bound |
| View immutable history | button | Not statically bound |
| View report | button | Not statically bound |
| Approve for internal sourcing | button | Yes; runtime evaluation unverified |
| Reject | button | Yes; runtime evaluation unverified |
| Keep under review | button | Yes; runtime evaluation unverified |
| Archive | button | Yes; runtime evaluation unverified |
| Recalculate | button | Yes; runtime evaluation unverified |
| Request more research | button | Yes; runtime evaluation unverified |
| Create internal handoff | button | Yes; runtime evaluation unverified |
| Calculate sensitivity | button | Yes; runtime evaluation unverified |

## P007 apps/web/src/app/intelligence/review-intelligence-workspace.component.ts

Routes: /intelligence/reviews

Headings: Review Intelligence; Review contexts; {{ context.name }}; Deterministic ingestion; Reviews; Deterministic analysis; What customers are saying; Feature requests; Product gaps and opportunity signals; Review evidence changed; Snapshots; Foundation integrity

Disclosures: Advanced / manual context

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Business Agent | a | Not statically bound |
| Product opportunities | a | Not statically bound |
| Open advanced research controls | button | Not statically bound |
| Create manual context | button | Yes; runtime evaluation unverified |
| {{ context.name }} {{ context.marketplace \|\| 'Unspecified' }} ? {{ context.status }} ? v{{ context.version }} | button | Not statically bound |
| Import local review | button | Yes; runtime evaluation unverified |
| Ingest fixture batch | button | Yes; runtime evaluation unverified |
| Analyze current snapshot | button | Yes; runtime evaluation unverified |
| Derive product gaps | button | Yes; runtime evaluation unverified |
| Compare review evidence | button | Yes; runtime evaluation unverified |
| Create immutable snapshot | button | Yes; runtime evaluation unverified |

## P008 apps/web/src/app/intelligence/competitor-intelligence-workspace.component.ts

Routes: /intelligence/competitors

Headings: Competitor intelligence; Research contexts; Competitor entities; Discovery and identity review; Pricing, positioning, and assortment; Competitive changes; Products in {{ context.marketplace \|\| 'this context' }}; Foundation integrity

Disclosures: Advanced / manual context

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Open advanced research controls | button | Not statically bound |
| Create manual context | button | Yes; runtime evaluation unverified |
| {{ context.marketplace \|\| 'Unspecified marketplace' }} {{ context.subject_type }} · {{ context.status }} · v{{ context.version }} | button | Not statically bound |
| Add entity | button | Yes; runtime evaluation unverified |
| Run local discovery | button | Yes; runtime evaluation unverified |
| Confirm | button | Yes; runtime evaluation unverified |
| Reject | button | Yes; runtime evaluation unverified |
| Mark ambiguous | button | Yes; runtime evaluation unverified |
| Run commercial analysis | button | Yes; runtime evaluation unverified |
| Run change comparison | button | Yes; runtime evaluation unverified |
| Add competitor product | button | Yes; runtime evaluation unverified |
| Mark confirmed | button | Yes; runtime evaluation unverified |

## P009 apps/web/src/app/intelligence/product-opportunity-workspace.component.ts

Routes: /intelligence/product-opportunities, /intelligence/product-opportunities/:opportunityId

Headings: detail() ? detail()!.name : 'Product opportunities'; Your product research results; {{ candidate.name }}; Why this product surfaced; Evidence-backed comparison; {{ candidate.name }}; What are you researching?; Current research; {{ item.name }}; Previous research; {{ item.name }}; Compare assessed opportunities; {{ item.name }}; Why VAYUJIT surfaced this product; How it relates to your goal; What this product means; Why VAYUJIT found this; Use case / customer problem; Key characteristics; Research keywords; Representative image; Observed price; Evidence gaps; Assessment summary; How this score was formed; What we know; Research objective; Customer / business context; Brand strategy; Tags; Research areas; Trend; Competition Intelligence; Customers / reviews; Suppliers / sourcing; Candidate evidence; Economics; Risk / completeness; Evidence; Sourcing economics; Sourcing economics; What we still do not know; Research gaps; Conflicting evidence; Continue research; History; Record a governed next action

Disclosures: View evidence and sources; Advanced technical details; Start a product opportunity; View previous research

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| All opportunities | button | Not statically bound |
| Intelligence | a | Not statically bound |
| Continue in Business Agent | a | Not statically bound |
| {{ primaryActionLabel(candidate) }} | button | Not statically bound |
| {{ isSelected(candidate.id) ? 'Remove from comparison' : 'Add to comparison' }} | button | Not statically bound |
| Research this product | button | Not statically bound |
| Select this product | button | Yes; runtime evaluation unverified |
| Compare selected products | button | Yes; runtime evaluation unverified |
| Select this product for supplier research | button | Yes; runtime evaluation unverified |
| Find suppliers | a | Not statically bound |
| Ask VAYUJIT | a | Not statically bound |
| Create opportunity | button | Yes; runtime evaluation unverified |
| View research | button | Not statically bound |
| View historical research | button | Not statically bound |
| Compare up to five assessments | button | Yes; runtime evaluation unverified |
| Back to current opportunities | button | Not statically bound |
| Find suppliers | a | Not statically bound |
| Select this product for supplier research | button | Yes; runtime evaluation unverified |
| Continue research with VAYUJIT | a | Not statically bound |
| Research market evidence | button | Yes; runtime evaluation unverified |
| Archive opportunity | button | Yes; runtime evaluation unverified |
| Load authoritative assessment | button | Yes; runtime evaluation unverified |
| Start authoritative assessment | button | Yes; runtime evaluation unverified |
| Continue in Business Agent | button | Not statically bound |
| Open Trend Intelligence | a | Not statically bound |
| Load Trend evidence | button | Yes; runtime evaluation unverified |
| Open Competitor Intelligence | a | Not statically bound |
| Load competition evidence | button | Yes; runtime evaluation unverified |
| Open Customer Reviews | a | Not statically bound |
| Load customer evidence | button | Yes; runtime evaluation unverified |
| View Suppliers | a | Not statically bound |
| Review Due Diligence | a | Not statically bound |
| Compare Sourcing Scenarios | a | Not statically bound |
| Review Economics & Decision Brief | a | Not statically bound |
| Load supplier evidence | button | Yes; runtime evaluation unverified |
| Load economics | button | Yes; runtime evaluation unverified |
| Load risk evidence | button | Yes; runtime evaluation unverified |
| Load sourcing economics | button | Yes; runtime evaluation unverified |
| Review evidence | button | Not statically bound |
| Refresh Trend projection | button | Yes; runtime evaluation unverified |
| Refresh Competition projection | button | Yes; runtime evaluation unverified |
| Refresh Customer projection | button | Yes; runtime evaluation unverified |
| Calculate Winning Product assessment | button | Yes; runtime evaluation unverified |
| Calculate demand intelligence | button | Yes; runtime evaluation unverified |
| Calculate economics | button | Yes; runtime evaluation unverified |
| Synthesize risk evidence | button | Yes; runtime evaluation unverified |
| Assess sourcing feasibility | button | Yes; runtime evaluation unverified |
| Ask VAYUJIT | a | Not statically bound |
| Load score history | button | Yes; runtime evaluation unverified |
| Request more research | button | Yes; runtime evaluation unverified |
| Watch | button | Yes; runtime evaluation unverified |
| Shortlist for human review | button | Yes; runtime evaluation unverified |

## P010 apps/web/src/app/auth/auth-page.component.ts

Routes: /setup, /login

Headings: {{ setup() ? 'Create your owner account' : 'Welcome back' }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ show() ? 'Hide' : 'Show' }} password | button | Not statically bound |
| {{ busy() ? 'Please wait…' : setup() ? 'Create owner' : 'Sign in' }} | button | Yes; runtime evaluation unverified |

## P011 apps/web/src/app/ads/ads-workspace.component.ts

Routes: /ads, /ads/create, /ads/calendar, /ads/accounts/:id, /ads/campaigns/:id, /ads/accounts, /ads/campaigns, /ads/analytics, /ads/recovery, /ads/settings

Headings: Operational ads workspace; Overview; Provider health; Quick actions; Attention and boundary; Accounts; Add Ads account; Campaigns; Create Ads campaign; {{ detail.campaign.name }}; Approved creatives and exact lineage; Analytics and profitability; Ads calendar; Recovery and failures; Ads settings; Server capabilities; {{ provider \| titlecase }}; Operational boundary

Disclosures: None found

Dialogs: 0; tables: 5.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create campaign | a | Not statically bound |
| {{ item.label }} | a | Not statically bound |
| Refresh | button | Not statically bound |
| Manage accounts | a | Not statically bound |
| Review campaigns | a | Not statically bound |
| Open recovery | a | Not statically bound |
| {{ showAccountForm ? 'Close form' : 'Add account' }} | button | Not statically bound |
| Save account | button | Yes; runtime evaluation unverified |
| {{ account.display_name }} | a | Not statically bound |
| Validate | button | Not statically bound |
| {{ account.enabled ? 'Disable' : 'Enable' }} | button | Not statically bound |
| Replace | button | Not statically bound |
| Remove | button | Not statically bound |
| Create campaign | a | Not statically bound |
| {{ campaign.name }} | a | Not statically bound |
| Cancel | a | Not statically bound |
| Back | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |
| Back to campaigns | a | Not statically bound |
| {{ detail.campaign.state === 'paused' ? 'Resume' : 'Pause' }} | button | Not statically bound |
| Reconcile | button | Not statically bound |
| Recovery | a | Not statically bound |
| {{ campaign.name }} | a | Not statically bound |
| {{ row.campaign \|\| row.campaign_id }} | a | Not statically bound |
| {{ action }} | button | Not statically bound |

## P012 apps/web/src/app/ads/marketing-plan.component.ts

Routes: /ads/marketing

Headings: Cross-channel marketing plans; Plan readiness; 12-step Marketing Plan wizard; {{ steps[wizardStep()] }}; Plans; {{ plan.objective \| titlecase }}; Saved plan v{{ plan.current_version }}; Canonical recommendations; Persisted history

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ wizardOpen() ? 'Close wizard' : 'Create plan' }} | button | Not statically bound |
| {{ index + 1 }}. {{ step }} | button | Not statically bound |
| Back | button | Yes; runtime evaluation unverified |
| Next | button | Not statically bound |
| Preview and confirm | button | Yes; runtime evaluation unverified |
| Refresh | button | Not statically bound |
| Review plan details | button | Not statically bound |
| Preview budget revision | button | Yes; runtime evaluation unverified |
| Confirm reviewed budget revision | button | Yes; runtime evaluation unverified |

## P013 apps/web/src/app/ads/ads-optimization.component.ts

Routes: /ads/optimization, /ads/recommendations, /ads/optimization-rules, /ads/anomalies, /ads/experiments, /ads/optimization-history, /ads/comparison

Headings: Optimization intelligence; Review queue; Recommendations; Optimization rules; Anomalies and fatigue; Experiments; Cross-provider comparison; Optimization history; Preview optimization

Disclosures: None found

Dialogs: 1; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Ads workspace | a | Not statically bound |
| {{ tab.label }} | a | Not statically bound |
| Evaluate campaigns | button | Not statically bound |
| Evaluate campaigns | button | Not statically bound |
| Preview | button | Not statically bound |
| Close | button | Not statically bound |

## P014 apps/web/src/app/operations/dashboard.component.ts

Routes: /dashboard

Headings: What should you do today?; Daily seller status; What are you trying to achieve?; {{ journeyGoalSummary(journey) }}; Needs your attention; Opportunities and findings; Your workspace; {{ metric.label }}; Take the next useful step; Workflow status; Recent activity

Disclosures: Advanced system health

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Review operational evidence | a | Not statically bound |
| Review stock ledger | a | Not statically bound |
| Review orders | a | Not statically bound |
| Review marketplace prerequisites | a | Not statically bound |
| Review sales and contribution evidence | a | Not statically bound |
| Start with Business Agent | a | Not statically bound |
| {{ item.action }} | a | Not statically bound |
| {{ item.action }} | a | Not statically bound |
| Open workspace | a | Not statically bound |
| + Start product research Find and compare opportunities worth investigating. | a | Not statically bound |
| + Open Action Center Review evidence-backed operational issues and next steps. | a | Not statically bound |
| + Find suppliers Review sourcing options for a product. | a | Not statically bound |
| + Create content Prepare content for a product or launch. | a | Not statically bound |
| + View calendar See planned work and upcoming activity. | a | Not statically bound |
| + Prepare a launch Continue into campaign and launch workflows. | a | Not statically bound |
| View details | a | Not statically bound |

## P015 apps/web/src/app/operations/action-center.component.ts

Routes: /operations/action-center

Headings: Action Center; Operational briefing; {{ total() }} matching issue(s); {{ item.title }}; Evidence and audit context; Resolution history; Automation policy

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Business Agent | a | Not statically bound |
| Refresh scan | button | Yes; runtime evaluation unverified |
| Inspect evidence | button | Not statically bound |
| Reopen | button | Yes; runtime evaluation unverified |
| Acknowledge | button | Yes; runtime evaluation unverified |
| Snooze 1 hour | button | Yes; runtime evaluation unverified |
| Resolve notice locally | button | Yes; runtime evaluation unverified |
| Open source | a | Not statically bound |
| Previous page | button | Yes; runtime evaluation unverified |
| Next page | button | Yes; runtime evaluation unverified |

## P016 apps/web/src/app/operations/launch-readiness.component.ts

Routes: /operations/launch-readiness

Headings: Launch readiness; {{ value.readyForReview }} of {{ value.total }} areas ready for HUMAN review; Warnings before a production-ready decision; {{ warning.title }}; {{ item.title }}; Prepare, review, then authorize

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to dashboard | a | Not statically bound |
| Review Action Center | a | Not statically bound |
| {{ warning.action }} | a | Not statically bound |
| {{ item.action }} | a | Not statically bound |
| Confirm business identity, timezone, and seller preferences. | a | Not statically bound |
| Prepare a real product, variant, SKU, images, costs, and listing draft. | a | Not statically bound |
| Record only HUMAN-confirmed physical stock and location evidence. | a | Not statically bound |
| Review marketplace account readiness; keep providers synthetic or read-only until separately approved. | a | Not statically bound |
| Create and verify an encrypted off-host backup plan before any production migration. | a | Not statically bound |
| Resolve evidence gaps and record the final HUMAN go-live decision. | a | Not statically bound |

## P017 apps/web/src/app/intelligence/sourcing-workspace.component.ts

Routes: /intelligence/sourcing

Headings: Requirements and supplier quotes; Know what is ready before you spend; Confirm the sourcing requirement; Prepare a supplier pricing request; Record supplier quotes; Validate samples and inspections; Complete landed-cost inputs; Quote comparison; Negotiation history; Sensitivity analysis; Capital and cash timeline; Critic findings; Supplier concentration; Human sourcing decision

Disclosures: Advanced requirement identifiers; Advanced RFQ controls; Advanced quote identifiers and provenance; Advanced sample/RFQ identifiers; Advanced local scenario tool; Advanced decision identifiers

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Return to this product and prepare its Catalog draft | a | Not statically bound |
| Open Product Opportunities | a | Not statically bound |
| Requirements | a | Not statically bound |
| RFQs | a | Not statically bound |
| Quotes | a | Not statically bound |
| Samples & inspection | a | Not statically bound |
| Comparison | a | Not statically bound |
| Negotiation | a | Not statically bound |
| Landed cost & economics | a | Not statically bound |
| Sensitivity | a | Not statically bound |
| Capital & cash | a | Not statically bound |
| Critic | a | Not statically bound |
| Concentration | a | Not statically bound |
| Decisions | a | Not statically bound |
| Confirm requirement | button | Yes; runtime evaluation unverified |
| Review Supplier Intelligence | a | Not statically bound |
| Prepare RFQ for review | button | Yes; runtime evaluation unverified |
| Record supplier quote | button | Yes; runtime evaluation unverified |
| Refresh recorded quotes | button | Not statically bound |
| Request sample locally | button | Yes; runtime evaluation unverified |
| Open landed-cost economics | a | Not statically bound |
| Calculate deterministic scenario | button | Yes; runtime evaluation unverified |
| Compare scenarios | a | Not statically bound |
| Review sensitivity | a | Not statically bound |
| Review capital requirement | a | Not statically bound |
| Open Decision Brief | a | Not statically bound |
| Record human decision | button | Yes; runtime evaluation unverified |

## P018 apps/web/src/app/intelligence/alibaba-discovery.component.ts

Routes: /intelligence/alibaba

Headings: Alibaba read-only discovery; Provider boundary; Run local discovery; Discovery history; Normalized listings

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Search suppliers | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |
| {{ run.query }} | button | Not statically bound |

## P019 apps/web/src/app/intelligence/indiamart-discovery.component.ts

Routes: /intelligence/indiamart

Headings: IndiaMART read-only discovery; Provider boundary; Run local discovery; Discovery history; Normalized listings

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Search suppliers | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |
| {{ run.query }} | button | Not statically bound |

## P020 apps/web/src/app/intelligence/tradeindia-discovery.component.ts

Routes: /intelligence/tradeindia

Headings: TradeIndia read-only discovery; Provider boundary; Run local discovery; Discovery history; Normalized listings

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Search suppliers | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |
| {{ run.query }} | button | Not statically bound |

## P021 apps/web/src/app/intelligence/global-sources-discovery.component.ts

Routes: /intelligence/global-sources

Headings: Global Sources read-only discovery; Provider boundary; Run local discovery; Discovery history; Normalized listings

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Search suppliers | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |
| {{ run.query }} | button | Not statically bound |

## P022 apps/web/src/app/intelligence/website-intelligence.component.ts

Routes: /intelligence/websites

Headings: Manufacturer & supplier websites; Runtime boundary; Website intelligence at a glance; Server-backed manufacturer list; Evidence detail; Business identity; Review boundary; Products / catalog; Offerings & match state; Capabilities; Facilities; Supplier website candidates; Catalog and supplier matches; Claim lifecycle; Certification status matrix; Observed terms and append-only history; Explainable risk review; Risk overview; Confidence components; Evidence comparison; Materiality and lineage; Review alerts; Allowlisted source profiles; Durable refresh jobs; Safe recovery actions; Unified website history; Website intelligence reports; Website research channel state; Refresh calendar; Operational linkage

Disclosures: None found

Dialogs: 0; tables: 11.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| {{ item.label }} | a | Not statically bound |
| Refresh list | button | Yes; runtime evaluation unverified |
| {{ row.name }} | button | Not statically bound |
| View | button | Not statically bound |
| View | button | Not statically bound |
| View | button | Not statically bound |
| Rerun | button | Yes; runtime evaluation unverified |
| Recover | button | Yes; runtime evaluation unverified |
| Apply filters | button | Yes; runtime evaluation unverified |
| View | button | Not statically bound |
| {{ productChannelLoading() ? 'Loading...' : 'View projection' }} | button | Yes; runtime evaluation unverified |
| Operations | a | Not statically bound |

## P023 apps/web/src/app/intelligence/external-research-workspace.component.ts

Routes: /intelligence/external

Headings: External Research; External research readiness; Provider registry; Approved source policy; Source profiles; Search history; Search results; Search detail; Approved fetch history; Fetch detail; Evidence Inspector; Evidence detail and freshness history; Source diversity and confidence; Contradiction review; {{ text(row, 'contradiction_type', 'Conflict') }}; Material change history; External research alerts; {{ text(row, 'title') }}; Safe recovery catalog; {{ text(row, 'failure_code', 'External failure') }}; Execution checkpoints, budgets, and rate limits; Unified external timeline; External research projection; Informational research events; Integrity, performance, and diagnostics; External storage inventory

Disclosures: None found

Dialogs: 0; tables: 8.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| {{ section.label }} | a | Not statically bound |
| Refresh | button | Yes; runtime evaluation unverified |
| Open Operations | a | Not statically bound |
| {{ productLoading() ? 'Loading...' : 'View projection' }} | button | Yes; runtime evaluation unverified |
| View Operations Control Center | a | Not statically bound |

## P024 apps/web/src/app/intelligence/autonomous-research.component.ts

Routes: /intelligence/autonomous

Headings: Autonomous research; Bounded missions and reviewable outcomes; Provider status; Safety policy; External research; Start a bounded mission; Mission history

Disclosures: Advanced runtime and provider details

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to intelligence | a | Not statically bound |
| Search approved provider | button | Yes; runtime evaluation unverified |
| {{ busy() ? 'Starting…' : 'Create mission' }} | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |
| Run local fixture | button | Yes; runtime evaluation unverified |

## P025 apps/web/src/app/intelligence/supplier-due-diligence.component.ts

Routes: /intelligence/due-diligence

Headings: Supplier Verification; Verification stays attached to the selected opportunity; What has been verified?; {{ supplierLabel() }}; Research plans

Disclosures: Advanced context details; Advanced supplier reference

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Return to supplier discovery | a | Not statically bound |
| Review supplier shortlist | a | Not statically bound |
| {{ assessingId === context.id ? 'Assessing existing evidence...' : isAssessed(context) ? 'Reassess existing evidence' : 'Assess existing evidence' }} | button | Yes; runtime evaluation unverified |
| Review economics and missing commercial inputs | a | Not statically bound |
| Research | button | Yes; runtime evaluation unverified |
| Research Selected Gaps | button | Yes; runtime evaluation unverified |
| Request more research | button | Yes; runtime evaluation unverified |
| Cancel research | button | Not statically bound |
| Waive | button | Yes; runtime evaluation unverified |
| Reopen | button | Yes; runtime evaluation unverified |
| Mark for human review | button | Not statically bound |
| Review Evidence | button | Not statically bound |

## P026 apps/web/src/app/intelligence/intelligence-workspace.component.ts

Routes: /intelligence

Headings: Winning product research; Research by purpose, then inspect the evidence; Understand the market signals; Understand suppliers and websites; Run bounded research; Review trust and recovery; Supplier discovery; Find suppliers; Add offline supplier; {{ selectedSupplier()?.display_name }}; Risk dimensions; Research projects; Create mission; Research missions; Research candidates; Candidate detail; {{ candidate.title }}; Signals and trend history; Opportunities; Opportunity detail; {{ detail.title }}; Score breakdown, demand, competition, pricing, trend, economics, capital, risk, legal/IP, rules, and provenance; Competitor intelligence; Review intelligence; Rule configuration and simulation; Research profile editor; Comparison workspace; Mission, score, report, and recovery history; Report workspace; {{ report.title }}; Evidence inspector

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to dashboard | a | Not statically bound |
| External Research | a | Not statically bound |
| Sourcing Scenarios | a | Not statically bound |
| Return to Guided Commerce | a | Not statically bound |
| Trend Intelligence | a | Not statically bound |
| Competitor Intelligence | a | Not statically bound |
| Customer Reviews | a | Not statically bound |
| Supplier Intelligence | a | Not statically bound |
| Website Intelligence | a | Not statically bound |
| Autonomous Research | a | Not statically bound |
| External Research | a | Not statically bound |
| Sources & evidence | a | Not statically bound |
| Research history | a | Not statically bound |
| Overview | a | Not statically bound |
| Missions | a | Not statically bound |
| Candidates | a | Not statically bound |
| Opportunities | a | Not statically bound |
| Rules | a | Not statically bound |
| Profiles | a | Not statically bound |
| Comparison | a | Not statically bound |
| Reports | a | Not statically bound |
| History | a | Not statically bound |
| Sources & evidence | a | Not statically bound |
| Suppliers | a | Not statically bound |
| Refresh suppliers | button | Yes; runtime evaluation unverified |
| {{ submitting() === 'supplier-search' ? 'Creating search...' : 'Create supplier search' }} | button | Yes; runtime evaluation unverified |
| {{ submitting() === 'supplier-research' ? 'Researching approved websites...' : 'Research approved supplier websites' }} | button | Yes; runtime evaluation unverified |
| Add offline supplier | button | Yes; runtime evaluation unverified |
| Inspect | button | Not statically bound |
| Shortlist | button | Yes; runtime evaluation unverified |
| Record partial verification | button | Not statically bound |
| Generate report | button | Not statically bound |
| Create project | button | Not statically bound |
| {{ submitting() === 'create-mission' ? 'Creating…' : 'Create mission' }} | button | Yes; runtime evaluation unverified |
| Run now | button | Yes; runtime evaluation unverified |
| {{ mission.status === 'paused' ? 'Resume' : 'Pause' }} | button | Yes; runtime evaluation unverified |
| Save schedule | button | Yes; runtime evaluation unverified |
| Save edits | button | Yes; runtime evaluation unverified |
| History | button | Not statically bound |
| {{ selectedCandidateIds().includes(candidate.id) ? '✓ Selected' : 'Compare' }} | button | Not statically bound |
| Details | button | Yes; runtime evaluation unverified |
| Compare {{ selectedCandidateIds().length }} selected | button | Yes; runtime evaluation unverified |
| Inspect | button | Yes; runtime evaluation unverified |
| Create profile | button | Yes; runtime evaluation unverified |

## P027 apps/web/src/app/campaigns/campaign-list.component.ts

Routes: /campaigns

Headings: Campaigns; {{ campaign.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Content calendar | a | Not statically bound |
| Create campaign | a | Not statically bound |
| {{ campaign.name }} | a | Not statically bound |

## P028 apps/web/src/app/campaigns/campaign-form.component.ts

Routes: /campaigns/new

Headings: Create Campaign

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Cancel | a | Not statically bound |
| Create Campaign | button | Yes; runtime evaluation unverified |

## P029 apps/web/src/app/campaigns/campaign-video.component.ts

Routes: /campaigns/:id/video/:activityId, /campaigns/:id/video

Headings: {{ campaignName() \|\| 'Campaign Video orchestration' }}; {{ selectedActivity()?.name }}; Recovery state; Activity history; Video Activities; {{ entry[0] }}; Exact Video Activities; {{ activity.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Campaign | a | Not statically bound |
| Review exact Video job | a | Not statically bound |
| Open detail | a | Not statically bound |

## P030 apps/web/src/app/campaigns/activity-form.component.ts

Routes: /campaigns/:id/activities/new

Headings: Add Campaign activity

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Cancel | a | Not statically bound |
| Add activity | button | Yes; runtime evaluation unverified |

## P031 apps/web/src/app/campaigns/dependency-editor.component.ts

Routes: /campaigns/:id/dependencies

Headings: Activity dependencies; Dependency order

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Campaign | a | Not statically bound |
| Add dependency | button | Yes; runtime evaluation unverified |
| Remove | button | Not statically bound |

## P032 apps/web/src/app/campaigns/campaign-detail.component.ts

Routes: /campaigns/:id

Headings: {{ value.name }}; Window; Progress; Readiness: {{ check.state }}; Conflicts; Activities; {{ activity.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Add activity | a | Not statically bound |
| Campaign Video | a | Not statically bound |
| Calendar | a | Not statically bound |
| Dependencies | a | Not statically bound |
| Review readiness | button | Not statically bound |
| Release | button | Yes; runtime evaluation unverified |
| Schedule all ready | button | Yes; runtime evaluation unverified |
| Pause | button | Yes; runtime evaluation unverified |
| Resume | button | Not statically bound |
| Cancel | button | Yes; runtime evaluation unverified |
| Reschedule Activity | button | Not statically bound |
| Create one catch-up | button | Not statically bound |
| Open job | a | Not statically bound |
| Open execution | a | Not statically bound |

## P033 apps/web/src/app/campaigns/content-calendar.component.ts

Routes: /calendar

Headings: Content calendar; Social publishing; {{ day.date \| date: 'd' }}; {{ slot.date \| date: 'EEE d' }}; {{ event.activity_name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Campaigns | a | Not statically bound |
| Month | button | Not statically bound |
| Week | button | Not statically bound |
| Agenda | button | Not statically bound |
| Previous | button | Not statically bound |
| Next | button | Not statically bound |
| {{ event.activity_name }} | a | Not statically bound |
| {{ event.activity_name }} | a | Not statically bound |

## P034 apps/web/src/app/social/social-workspace.component.ts

Routes: /social, /social/compose, /social/channel, /social/accounts, /social/analytics, /social/posts/:id, /social/recovery, /social/settings

Headings: Social workspace; {{ post.platform }} / {{ post.content_type }} SocialPost; History; Image draft review; Image-only draft; Compose Video post; Product Channel - Social Video; Video Recovery; Accounts and diagnostics; Video analytics; Video publication readiness; Connected accounts; Platforms; Recent Video posts; Recoverable Video failures; Analytics Synthetic

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Refresh | button | Yes; runtime evaluation unverified |
| Overview | a | Not statically bound |
| Compose | a | Not statically bound |
| Calendar | a | Not statically bound |
| Accounts | a | Not statically bound |
| Analytics | a | Not statically bound |
| Recovery | a | Not statically bound |
| Save draft caption | button | Yes; runtime evaluation unverified |
| Preview image draft | button | Yes; runtime evaluation unverified |
| Approve image draft — do not publish | button | Yes; runtime evaluation unverified |
| Save image-only draft | button | Yes; runtime evaluation unverified |
| Preview exact post | button | Yes; runtime evaluation unverified |
| Save reviewed Video draft | button | Yes; runtime evaluation unverified |
| Confirm {{ draft.mode === 'now' ? 'Publish Now' : 'Schedule' }} | button | Yes; runtime evaluation unverified |
| Back | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |
| Load channel | button | Not statically bound |
| Preview Video Update | button | Yes; runtime evaluation unverified |
| Open SocialPost | a | Not statically bound |
| {{ label(action) }} | button | Not statically bound |
| Open details | a | Not statically bound |

## P035 apps/web/src/app/marketplaces/marketplace-home.component.ts

Routes: /marketplaces

Headings: Marketplace overview; Accounts; Listings; Inventory; Orders; Settlements; Profitability; Financial workspace; Channel health; Combined totals ({{ total.currency }})

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Accounts Connected accounts and validation status. | a | Not statically bound |
| Listings Active, processing, and attention-required listings. | a | Not statically bound |
| Inventory Explicit per-channel stock and synchronization. | a | Not statically bound |
| Orders Normalized buyer-safe order lifecycle. | a | Not statically bound |
| Settlements Normalized gross, refunds, fees, and net. | a | Not statically bound |
| Profitability Contribution with explicit cost availability. | a | Not statically bound |
| Financial workspace Sales facts, fee evidence, product costs, and settlement reconciliation. | a | Not statically bound |
| Open channel | a | Not statically bound |

## P036 apps/web/src/app/marketplaces/marketplace-video.component.ts

Routes: /marketplaces/video

Headings: Marketplace video attachment; Overview; Attachment workspace; Attachment preview; Target; Exact Video; Readiness; Video Attachments; Pending Operations & Recovery; {{ item.marketplace }} - {{ item.error_code \|\| 'Video failure' }}; Reconciliation; History; Diagnostics

Disclosures: None found

Dialogs: 0; tables: 4.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Refresh data | button | Yes; runtime evaluation unverified |
| {{ section.label }} | button | Not statically bound |
| Preview attachment | button | Yes; runtime evaluation unverified |
| Preview update | button | Yes; runtime evaluation unverified |
| Open listings | a | Not statically bound |
| {{ confirming() ? 'Submitting...' : 'Confirm attachment' }} | button | Yes; runtime evaluation unverified |
| Close preview | button | Not statically bound |
| Reconcile | button | Not statically bound |
| Preview update | button | Not statically bound |
| Open recovery | button | Not statically bound |
| {{ action }} | button | Not statically bound |
| Reconcile authorized mappings | button | Yes; runtime evaluation unverified |

## P037 apps/web/src/app/marketplaces/flipkart-workspace.component.ts

Routes: /marketplaces/flipkart, /marketplaces/listings/:id/flipkart

Headings: Flipkart operations; Account; Listings; Create listing; Listing editor: {{ listing.title }}; Blocking issues; Warnings; Information; Orders and fulfilment; Financials and profitability; Diagnostics

Disclosures: None found

Dialogs: 0; tables: 4.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ tab }} | button | Not statically bound |
| Configure | button | Not statically bound |
| Validate | button | Not statically bound |
| Revalidate | button | Not statically bound |
| {{ account.enabled ? 'Disable' : 'Enable' }} | button | Not statically bound |
| Replace credential | button | Not statically bound |
| Remove credential | button | Not statically bound |
| Edit | button | Not statically bound |
| Create draft | button | Not statically bound |
| {{ tab }} | button | Not statically bound |
| Build variant matrix | button | Not statically bound |
| Remove | button | Not statically bound |
| Save variant matrix | button | Yes; runtime evaluation unverified |
| Add media mapping | button | Not statically bound |
| Review and confirm price | button | Yes; runtime evaluation unverified |
| Preview and confirm inventory | button | Not statically bound |
| Refresh readiness | button | Not statically bound |
| Review exact listing | button | Yes; runtime evaluation unverified |
| Authorize local execution | button | Yes; runtime evaluation unverified |
| Confirm and submit | button | Yes; runtime evaluation unverified |
| Revoke authorization | button | Yes; runtime evaluation unverified |
| Refresh remote state | button | Not statically bound |
| Review drift | button | Not statically bound |
| Keep remote | button | Not statically bound |
| Confirmed overwrite | button | Not statically bound |
| Import orders | button | Not statically bound |
| Import settlements | button | Not statically bound |
| Back to Marketplace overview | a | Not statically bound |

## P038 apps/web/src/app/marketplaces/meesho-workspace.component.ts

Routes: /marketplaces/meesho, /marketplaces/listings/:id/meesho

Headings: Meesho operations; Account; Listings; Create listing; Listing editor: {{ listing.title }}; Blocking issues; Warnings; Information; Orders and fulfilment; Financials and profitability; Diagnostics

Disclosures: None found

Dialogs: 0; tables: 4.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ tab }} | button | Not statically bound |
| Configure | button | Not statically bound |
| Validate | button | Not statically bound |
| Revalidate | button | Not statically bound |
| {{ account.enabled ? 'Disable' : 'Enable' }} | button | Not statically bound |
| Replace credential | button | Not statically bound |
| Remove credential | button | Not statically bound |
| Edit | button | Not statically bound |
| Create draft | button | Not statically bound |
| {{ tab }} | button | Not statically bound |
| Build variant matrix | button | Not statically bound |
| Remove | button | Not statically bound |
| Save variant matrix | button | Yes; runtime evaluation unverified |
| Add media mapping | button | Not statically bound |
| Review and confirm price | button | Yes; runtime evaluation unverified |
| Preview and confirm inventory | button | Not statically bound |
| Refresh readiness | button | Not statically bound |
| Confirm and submit | button | Yes; runtime evaluation unverified |
| Refresh remote state | button | Not statically bound |
| Review drift | button | Not statically bound |
| Keep remote | button | Not statically bound |
| Confirmed overwrite | button | Not statically bound |
| Import orders | button | Not statically bound |
| Import settlements | button | Not statically bound |
| Back to Marketplace overview | a | Not statically bound |

## P039 apps/web/src/app/marketplaces/amazon-workspace.component.ts

Routes: /marketplaces/amazon, /marketplaces/listings/:id/amazon

Headings: Amazon Marketplace workspace; Account and connector health; Listing editor; Prepare unpublished Amazon draft; Server-driven readiness {{ ready.ready ? 'Ready' : 'Blocked' }}; Blocking; Warnings; Informational; Variant editor and option matrix; Media editor; Orders and fulfilment; Returns and refunds; Settlement and profitability; Drift matrix and guarded overwrite

Disclosures: Lines

Dialogs: 0; tables: 6.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Configure account | button | Not statically bound |
| Validate | button | Not statically bound |
| {{ current.enabled ? 'Disable' : 'Enable' }} | button | Not statically bound |
| Replace credential | button | Not statically bound |
| Remove credential | button | Not statically bound |
| Refresh diagnostics | button | Not statically bound |
| Prepare local Amazon draft | button | Yes; runtime evaluation unverified |
| Preview readiness | button | Not statically bound |
| Approve listing for controlled submission | button | Yes; runtime evaluation unverified |
| Issue one-time execution authorization | button | Yes; runtime evaluation unverified |
| Submit approved listing | button | Yes; runtime evaluation unverified |
| Reconcile remote status | button | Not statically bound |
| Confirm price update | button | Yes; runtime evaluation unverified |
| Confirm inventory update | button | Not statically bound |
| Revoke authorization | button | Not statically bound |
| Build matrix | button | Not statically bound |
| Add variant | button | Not statically bound |
| Save variants | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Remove | button | Not statically bound |
| Preview local main image | button | Not statically bound |
| Confirm exact local main image | button | Yes; runtime evaluation unverified |
| Add media | button | Not statically bound |
| Save ordered media | button | Yes; runtime evaluation unverified |
| Move up | button | Yes; runtime evaluation unverified |
| Move down | button | Yes; runtime evaluation unverified |
| Remove | button | Not statically bound |
| Import orders | button | Not statically bound |
| Import return records | button | Not statically bound |
| Import settlements and fees | button | Not statically bound |
| Review drift | button | Not statically bound |
| Keep remote | button | Not statically bound |
| Overwrite remote (confirm) | button | Not statically bound |

## P040 apps/web/src/app/marketplaces/marketplace-accounts.component.ts

Routes: /marketplaces/accounts

Headings: Marketplace accounts; Read-only connectivity center; Provider capabilities; {{ capability.provider \| titlecase }}; {{ account.display_name }} import history

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Refresh | button | Yes; runtime evaluation unverified |
| Add account | button | Not statically bound |
| Validate | button | Not statically bound |
| {{ account.enabled ? 'Disable' : 'Enable' }} | button | Not statically bound |
| {{ syncing() === account.id + ':' + operation ? 'Importing…' : 'Import ' + operation }} | button | Yes; runtime evaluation unverified |

## P041 apps/web/src/app/marketplaces/marketplace-listings.component.ts

Routes: /marketplaces/listings

Headings: Marketplace listings

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |


## P042 apps/web/src/app/marketplaces/opening-stock.component.ts

Routes: /marketplaces/inventory/opening

Headings: Add opening stock; Opening stock needs attention; Opening stock recorded; What next?; Review opening stock; 1. Choose an existing product; Current canonical stock for this product; 2. Record your counted units

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to inventory | a | Not statically bound |
| Return to inventory | a | Not statically bound |
| {{ busy() ? 'Saving and verifying…' : uncertain() ? 'Retry identical opening request' : 'Confirm opening stock' }} | button | Yes; runtime evaluation unverified |
| Edit review | button | Yes; runtime evaluation unverified |
| Find products | button | Not statically bound |
| Create a product | a | Not statically bound |
| Previous products | button | Yes; runtime evaluation unverified |
| Next products | button | Yes; runtime evaluation unverified |
| Review opening stock | button | Yes; runtime evaluation unverified |
| Cancel | a | Not statically bound |

## P043 apps/web/src/app/marketplaces/unified-inventory.component.ts

Routes: /marketplaces/inventory

Headings: Unified inventory; Movement ledger for {{ item.internal_sku }}; Map a channel SKU for {{ item.internal_sku }}

Disclosures: None found

Dialogs: 0; tables: 2.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Add opening stock | a | Not statically bound |
| Refresh | button | Not statically bound |
| {{ selectedItem()?.id === item.id ? 'Close adjustment' : 'Adjust stock' }} | button | Not statically bound |
| {{ ledgerItem()?.id === item.id ? 'Hide ledger' : 'View ledger' }} | button | Not statically bound |
| {{ mappingItem()?.id === item.id ? 'Hide mapping' : 'Map channel SKU' }} | button | Not statically bound |
| {{ saving() ? 'Saving...' : 'Record adjustment' }} | button | Yes; runtime evaluation unverified |
| {{ mappingSaving() ? 'Saving...' : 'Save mapping' }} | button | Yes; runtime evaluation unverified |
| Cancel | button | Not statically bound |

## P044 apps/web/src/app/marketplaces/unified-orders.component.ts

Routes: /marketplaces/orders

Headings: Unified orders; Order {{ order.remote_order_id }}; {{ line.title \|\| line.marketplace_sku \|\| 'Order line' }}

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Review account prerequisites | a | Not statically bound |
| Review inventory | a | Not statically bound |
| Review financial evidence | a | Not statically bound |
| Refresh | button | Not statically bound |
| {{ selectedOrder()?.id === order.id ? 'Hide details' : 'View details' }} | button | Not statically bound |
| Review this product | a | Not statically bound |
| Review this product inventory | a | Not statically bound |

## P045 apps/web/src/app/marketplaces/marketplace-settlements.component.ts

Routes: /marketplaces/settlements

Headings: Marketplace settlements

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |


## P046 apps/web/src/app/marketplaces/marketplace-analytics.component.ts

Routes: /marketplaces/analytics

Headings: Marketplace analytics

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |


## P047 apps/web/src/app/marketplaces/financial-workspace.component.ts

Routes: /marketplaces/financials

Headings: Sales & profitability; Financial alerts; Revenue trend; Marketplace comparison; Refund impact; Fee breakdown; Product profitability; Settlement reconciliation; Business Agent guidance

Disclosures: None found

Dialogs: 0; tables: 4.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Review source orders | a | Not statically bound |
| Review operational recommendations | a | Not statically bound |
| Review product cost context | a | Not statically bound |
| Refresh evidence | button | Not statically bound |
| {{ row['product_id'] }} | a | Not statically bound |

## P048 apps/web/src/app/brands/brand-list.component.ts

Routes: /brands

Headings: Brands; {{ brand.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create brand | a | Not statically bound |
| Apply | button | Not statically bound |
| {{ brand.name }} | a | Not statically bound |
| View | a | Not statically bound |
| Edit | a | Not statically bound |
| Activate | button | Not statically bound |
| Archive | button | Not statically bound |
| Restore | button | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P049 apps/web/src/app/brands/brand-form.component.ts

Routes: /brands/new, /brands/:id/edit

Headings: {{ editing() ? 'Edit brand' : 'Create brand' }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Cancel | a | Not statically bound |
| {{ saving() ? 'Saving…' : 'Save brand' }} | button | Yes; runtime evaluation unverified |

## P050 apps/web/src/app/brands/brand-details.component.ts

Routes: /brands/:id

Headings: {{ brand()!.name }}; Recent activity

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back | a | Not statically bound |
| Edit | a | Not statically bound |
| Set active | button | Not statically bound |
| Archive | button | Not statically bound |
| Restore | button | Not statically bound |

## P051 apps/web/src/app/products/product-list.component.ts

Routes: /products

Headings: Products; {{ product.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create product | a | Not statically bound |
| Apply | button | Not statically bound |
| Manage brands | a | Not statically bound |
| {{ product.name }} | a | Not statically bound |
| View | a | Not statically bound |
| Edit | a | Not statically bound |
| Activate | button | Not statically bound |
| Move to draft | button | Not statically bound |
| Archive | button | Not statically bound |
| Restore | button | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P052 apps/web/src/app/catalog/catalog-workspace.component.ts

Routes: /catalog, /catalog/:id

Headings: Catalog product; detail()!.product.name; Change not completed; Product context; Product images; Economics readiness; Supplier and quotation context; Business Agent guidance; {{ readiness()!.readiness === 'BLOCKED' ? 'More information is required' : 'Catalog drafts reviewed locally' }}; Listing drafts; {{ channelLabel(channel) }}; Variants; Product master & listing preparation; {{ product.name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| ← Back to Seller Catalog | a | Not statically bound |
| Product record | a | Not statically bound |
| Edit product | a | Not statically bound |
| Reload saved product | button | Not statically bound |
| Record counted opening stock | a | Not statically bound |
| Review stock ledger | a | Not statically bound |
| Marketplace readiness | a | Not statically bound |
| Return to research and suppliers | a | Not statically bound |
| Upload a product image | a | Not statically bound |
| Refresh image library | button | Yes; runtime evaluation unverified |
| {{ imageSaving() ? 'Saving…' : 'Add image' }} | button | Yes; runtime evaluation unverified |
| Set primary | button | Yes; runtime evaluation unverified |
| Remove | button | Not statically bound |
| Prepare this product's economics | a | Not statically bound |
| Review this product's economics | a | Not statically bound |
| Review this product's suppliers | a | Not statically bound |
| Review local requirements and quotations | a | Not statically bound |
| Open Business Agent | a | Not statically bound |
| Use primary product image | button | Yes; runtime evaluation unverified |
| {{ draftSaving() === draft.id ? 'Saving…' : 'Save draft' }} | button | Yes; runtime evaluation unverified |
| Approve as HUMAN | button | Yes; runtime evaluation unverified |
| Start {{ channelLabel(channel) }} draft | button | Yes; runtime evaluation unverified |
| {{ variantSaving() ? 'Saving…' : 'Add variant' }} | button | Yes; runtime evaluation unverified |
| {{ variantSaving() === variant.id ? 'Saving…' : 'Save variant' }} | button | Yes; runtime evaluation unverified |
| Archive | button | Not statically bound |
| Record stock for {{ variant.title \|\| variant.variant_key }} | a | Not statically bound |
| Create product | a | Not statically bound |
| Create a product | a | Not statically bound |
| Review opportunities | a | Not statically bound |
| Open catalog workspace | a | Not statically bound |
| View product | a | Not statically bound |

## P053 apps/web/src/app/products/product-form.component.ts

Routes: /products/new, /products/:id/edit

Headings: editing() ? 'Edit product' : 'Create product'

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create brand | a | Not statically bound |
| Cancel | a | Not statically bound |
| {{ saving() ? 'Saving...' : 'Save product' }} | button | Yes; runtime evaluation unverified |

## P054 apps/web/src/app/marketplaces/product-channel-view.component.ts

Routes: /products/:id/channels

Headings: product()?.product?.name ? product()!.product.name + ' — marketplace preparation' : 'Product marketplace preparation'; Other content destinations — not seller accounts; Marketplace Video; {{ video.marketplace }}

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Return to this Catalog product | a | Not statically bound |
| Review seller-account prerequisites | a | Not statically bound |
| Record counted opening stock | a | Not statically bound |
| Prepare local draft | a | Not statically bound |
| Review saved listing | a | Not statically bound |
| {{ action }} | button | Not statically bound |

## P055 apps/web/src/app/products/product-media.component.ts

Routes: /products/:id/media

Headings: Image and video usage; Marketplace Video usage {{ videoUsage().length }}; {{ usage.marketplace }}; {{ group.label }} {{ group.items.length }}; {{ item.operation \|\| 'Uploaded asset' }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to product | a | Not statically bound |
| Open Video workspace | a | Not statically bound |
| Review | a | Not statically bound |

## P056 apps/web/src/app/products/product-details.component.ts

Routes: /products/:id

Headings: Product details; product()!.name; Commerce and creation context; Content; Pricing; Inventory and shipping; Recent activity

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back | a | Not statically bound |
| Open catalog workspace | a | Not statically bound |
| Edit | a | Not statically bound |
| View Product Channels | a | Not statically bound |
| View Product Media | a | Not statically bound |
| Marketplace Listings | a | Not statically bound |
| Activate | button | Not statically bound |
| Move to draft | button | Not statically bound |
| Archive | button | Not statically bound |
| Restore to draft | button | Not statically bound |

## P057 apps/web/src/app/ai/ai-home.component.ts

Routes: /ai

Headings: AI content studio; Provider; Generation history; Provider settings; Recent requests

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Generate content | a | Not statically bound |
| View history | a | Not statically bound |
| View usage | a | Not statically bound |
| Configure and validate real provider | a | Not statically bound |
| Review v{{ item.version_number }} | a | Not statically bound |

## P058 apps/web/src/app/ai/ai-generate.component.ts

Routes: /ai/generate

Headings: Generate product content; Generation summary

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back | a | Not statically bound |
| Open provider settings | a | Not statically bound |
| {{ busy() ? 'Generating...' : 'Generate review draft' }} | button | Yes; runtime evaluation unverified |

## P059 apps/web/src/app/ai/ai-studio.component.ts

Routes: /ai/studio

Headings: AI Product Content + SEO Studio; Generate content; Latest artifacts; SEO Studio; Brand Voice; Diagnostics

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| SEO & keywords | a | Not statically bound |
| Bulk generation | a | Not statically bound |
| AI overview | a | Not statically bound |
| Generate | a | Not statically bound |
| Artifacts | a | Not statically bound |
| SEO Studio | a | Not statically bound |
| Brand Voice | a | Not statically bound |
| Diagnostics | a | Not statically bound |
| {{ busy() ? 'Generating...' : 'Generate deterministic draft' }} | button | Yes; runtime evaluation unverified |
| Refresh generation status | button | Yes; runtime evaluation unverified |
| Retry failed content | button | Yes; runtime evaluation unverified |
| Refresh artifacts | button | Not statically bound |
| Review | a | Not statically bound |
| Analyze SEO | button | Yes; runtime evaluation unverified |
| Manage Brand Voices | a | Not statically bound |
| Manage Presets | a | Not statically bound |
| View Usage | a | Not statically bound |
| Provider settings | a | Not statically bound |

## P060 apps/web/src/app/ai/ai-image-review.component.ts

Routes: /ai/images/assets/:outputId

Headings: Image review; Generated image; Lineage; Readiness and classification; Comparison and history

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Images | a | Not statically bound |
| Approve exact output | button | Yes; runtime evaluation unverified |
| Reject with feedback | button | Yes; runtime evaluation unverified |
| Regenerate | button | Yes; runtime evaluation unverified |
| Refresh exact output | button | Yes; runtime evaluation unverified |
| Retry exact image job | button | Yes; runtime evaluation unverified |
| Compare exact versions | button | Yes; runtime evaluation unverified |
| Show history | button | Yes; runtime evaluation unverified |

## P061 apps/web/src/app/ai/ai-video-bulk.component.ts

Routes: /ai/video/bulk

Headings: Bulk Video Studio; Reopen saved operation; 1. Plan; 2. Review and confirm; Operation {{ item.status }}; Persisted recovery history

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| ← AI Video Studio | a | Not statically bound |
| Open operation | button | Yes; runtime evaluation unverified |
| Preview plan | button | Yes; runtime evaluation unverified |
| Confirm and queue | button | Yes; runtime evaluation unverified |
| Refresh status | button | Yes; runtime evaluation unverified |
| Retry failed children | button | Yes; runtime evaluation unverified |
| Cancel remaining children | button | Yes; runtime evaluation unverified |
| Review child Video job | a | Not statically bound |

## P062 apps/web/src/app/ai/ai-video.component.ts

Routes: /ai/video

Headings: AI video studio; Video Projects; Generate Video; Videos; Scripts; {{ script['name'] }} v{{ script['version'] }}; Storyboards; Version {{ board['version'] \|\| '-' }}; Storyboard v{{ board['version'] }} editor; Review Videos; Safe player; Lineage & readiness; Presets & Styles; Style: {{ style['name'] \|\| style['key'] \|\| style['id'] }}; {{ preset['name'] \|\| 'Preset' }} v{{ preset['version'] \|\| '-' }}; Captions; History & Recovery; Recovery projection; Usage; Diagnostics

Disclosures: Advanced source media reference

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ view.label }} | a | Not statically bound |
| Refresh | button | Not statically bound |
| Bulk Video | a | Not statically bound |
| Create Video | a | Not statically bound |
| Open Storyboards | a | Not statically bound |
| Review Videos | a | Not statically bound |
| Manage Presets | a | Not statically bound |
| View Diagnostics | a | Not statically bound |
| Back | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |
| {{ queueing() ? 'Queueing-' : 'Queue Video' }} | button | Yes; runtime evaluation unverified |
| Open review | button | Not statically bound |
| Refresh | button | Not statically bound |
| Open / edit | button | Not statically bound |
| Approve | button | Not statically bound |
| Reject | button | Not statically bound |
| Regenerate | button | Not statically bound |
| Compare | button | Not statically bound |
| History | button | Not statically bound |
| Refresh | button | Not statically bound |
| Open editor | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Remove | button | Not statically bound |
| Move up | button | Yes; runtime evaluation unverified |
| Move down | button | Yes; runtime evaluation unverified |
| Add scene | button | Not statically bound |
| Save | button | Not statically bound |
| Validate | button | Not statically bound |
| Preview | button | Not statically bound |
| Approve | button | Not statically bound |
| Approve | button | Not statically bound |
| Reject | button | Not statically bound |
| Compare | button | Not statically bound |
| Recovery | button | Not statically bound |
| Refresh | button | Not statically bound |
| Preview | button | Not statically bound |
| Set default | button | Not statically bound |
| {{ style['archived_at'] ? 'Restore' : 'Archive' }} | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Preview | button | Not statically bound |
| {{ preset['archived_at'] ? 'Restore' : 'Archive' }} | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Add track | button | Yes; runtime evaluation unverified |
| Refresh tracks | button | Yes; runtime evaluation unverified |
| Approve | button | Not statically bound |
| Export WebVTT | button | Not statically bound |
| Refresh | button | Yes; runtime evaluation unverified |
| Retry failed Video | button | Yes; runtime evaluation unverified |
| Refresh | button | Not statically bound |

## P063 apps/web/src/app/ai/ai-image-bulk.component.ts

Routes: /ai/images/bulk

Headings: Bulk image generation; New bulk generation; 10. Review plan; Bulk operation: {{ current.status }}

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Single image | a | Not statically bound |
| {{ busy() ? 'Working...' : 'Review plan' }} | button | Yes; runtime evaluation unverified |
| Queue bulk generation | button | Yes; runtime evaluation unverified |
| Refresh operation status | button | Yes; runtime evaluation unverified |
| Review | a | Not statically bound |
| Retry | button | Not statically bound |

## P064 apps/web/src/app/ai/ai-image-studio.component.ts

Routes: /ai/images

Headings: AI image studio; Generate image; Generation {{ generation()!.status }}; Safety and readiness

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Bulk images | a | Not statically bound |
| Content studio | a | Not statically bound |
| Media library | a | Not statically bound |
| {{ busy() ? 'Queueing...' : 'Queue deterministic image' }} | button | Yes; runtime evaluation unverified |
| Review output | a | Not statically bound |

## P065 apps/web/src/app/ai/ai-seo.component.ts

Routes: /ai/studio/seo

Headings: SEO and content intelligence; {{ currentAnalysis.seo_type === 'website' ? 'Website SEO' : 'Marketplace Search Optimization' }} - {{ currentAnalysis.channel }}; Findings; Keyword Sets; Tags; Analysis History

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Bulk generation | a | Not statically bound |
| Overview | button | Not statically bound |
| Website SEO | button | Not statically bound |
| Marketplace Search | button | Not statically bound |
| Keywords | button | Not statically bound |
| Tags | button | Not statically bound |
| Analysis History | button | Not statically bound |
| {{ loading() ? 'Analyzing...' : 'Analyze' }} | button | Yes; runtime evaluation unverified |
| Edit | button | Not statically bound |
| Regenerate | button | Not statically bound |
| Re-analyze | button | Not statically bound |
| Open keywords | button | Not statically bound |
| Save Keyword Set | button | Yes; runtime evaluation unverified |
| AI Suggestions | button | Not statically bound |
| Refresh saved metadata | button | Not statically bound |
| Edit {{ item.name }} | button | Not statically bound |
| Save tags | button | Yes; runtime evaluation unverified |
| Refresh saved metadata | button | Not statically bound |
| Edit {{ item.name }} | button | Not statically bound |
| Refresh history | button | Not statically bound |
| Open saved analysis | button | Not statically bound |
| Re-analyze saved snapshot | button | Not statically bound |
| Review analyzed artifact | a | Not statically bound |

## P066 apps/web/src/app/ai/ai-bulk.component.ts

Routes: /ai/studio/bulk

Headings: Bulk generation; New bulk generation; Plan review; Bulk operations; Operation details

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| AI Studio | a | Not statically bound |
| Review plan | button | Yes; runtime evaluation unverified |
| Queue {{ preview()!.total_outputs }} outputs | button | Yes; runtime evaluation unverified |
| Refresh history | button | Not statically bound |
| Open details | button | Not statically bound |
| Cancel remaining | button | Yes; runtime evaluation unverified |
| Retry failed | button | Yes; runtime evaluation unverified |
| Review | a | Not statically bound |
| Retry | button | Not statically bound |
| Cancel | button | Not statically bound |

## P067 apps/web/src/app/ai/ai-artifact.component.ts

Routes: /ai/studio/artifacts/:id/compare, /ai/artifacts/:id, /approvals/:id

Headings: Content review; Compare versions; {{ field[0] }}; {{ field[0] }}; Locale actions; Channel-specific content; {{ item.content.product_title }}; Key features; SEO; Social caption; Edit structured content; Approved handoff

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| History | a | Not statically bound |
| Back to Workflow | a | Not statically bound |
| Workflow | a | Not statically bound |
| Translate exact Artifact | button | Yes; runtime evaluation unverified |
| Save as new version | button | Yes; runtime evaluation unverified |
| Cancel | button | Not statically bound |
| Edit structured content | button | Not statically bound |
| Use in Marketplace Listing | button | Yes; runtime evaluation unverified |
| Use in Campaign | button | Yes; runtime evaluation unverified |
| Approve | button | Yes; runtime evaluation unverified |
| Regenerate selected current version | button | Yes; runtime evaluation unverified |
| Reject | button | Yes; runtime evaluation unverified |
| Open full Artifact details | a | Not statically bound |
| Return to approval queue | a | Not statically bound |

## P068 apps/web/src/app/ai/ai-history.component.ts

Routes: /ai/history

Headings: AI generation history

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Generate | a | Not statically bound |
| Filter | button | Not statically bound |
| Open | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P069 apps/web/src/app/ai/brand-voice-workspace.component.ts

Routes: /ai/brand-voices

Headings: Brand Voices

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ editing ? 'Save new version' : 'Create Brand Voice' }} | button | Not statically bound |
| Edit | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Set default | button | Not statically bound |
| Preview | button | Not statically bound |
| Archive | button | Not statically bound |

## P070 apps/web/src/app/ai/preset-workspace.component.ts

Routes: /ai/presets

Headings: Generation Presets

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create preset | button | Not statically bound |
| Duplicate | button | Not statically bound |
| Set default | button | Not statically bound |
| Archive | button | Not statically bound |

## P071 apps/web/src/app/ai/ai-usage.component.ts

Routes: /ai/usage

Headings: AI usage; Requests; Successful / failed; Retries; Tokens; Estimated cost; Usage history

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back | a | Not statically bound |
| Export last 31 days | button | Not statically bound |

## P072 apps/web/src/app/ai/ai-provider-settings.component.ts

Routes: /settings/ai/providers, /settings/ai/providers/openai-compatible

Headings: OpenAI-compatible provider; Status: {{ statusLabel(saved) }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to settings | a | Not statically bound |
| Save configuration | button | Yes; runtime evaluation unverified |
| Validate configuration | button | Yes; runtime evaluation unverified |
| Discover models | button | Yes; runtime evaluation unverified |
| Remove saved key | button | Yes; runtime evaluation unverified |

## P073 apps/web/src/app/publishing/wordpress-settings.component.ts

Routes: /settings/publishing/connectors/wordpress

Headings: WordPress; Connection state

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Publishing | a | Not statically bound |
| Save configuration | button | Yes; runtime evaluation unverified |
| Validate | button | Yes; runtime evaluation unverified |
| {{ config.enabled ? 'Disable' : 'Enable' }} | button | Yes; runtime evaluation unverified |
| Remove application credential | button | Yes; runtime evaluation unverified |

## P074 apps/web/src/app/publishing/shopify-settings.component.ts

Routes: /settings/publishing/connectors/shopify

Headings: Shopify; Connection state; Remote discovery; Collections; Publications

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Publishing | a | Not statically bound |
| Save configuration | button | Yes; runtime evaluation unverified |
| Validate | button | Yes; runtime evaluation unverified |
| {{ config.enabled ? 'Disable' : 'Enable' }} | button | Yes; runtime evaluation unverified |
| Remove stored token | button | Yes; runtime evaluation unverified |
| Refresh | button | Yes; runtime evaluation unverified |

## P075 apps/web/src/app/media/media-list.component.ts

Routes: /media

Headings: Media Library; No media found; {{ item.safe_filename }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Upload image | a | Not statically bound |
| Apply | button | Not statically bound |
| {{ listView() ? 'Grid view' : 'List view' }} | button | Not statically bound |
| {{ item.safe_filename }} | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P076 apps/web/src/app/media/media-upload.component.ts

Routes: /media/upload

Headings: Upload image; {{ item.duplicate_reused ? 'Existing media reused' : 'Upload complete' }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to product images | a | Not statically bound |
| Back to library | a | Not statically bound |
| {{ busy() ? 'Validating and storing…' : 'Upload securely' }} | button | Yes; runtime evaluation unverified |
| Cancel selection | button | Yes; runtime evaluation unverified |
| View media details | a | Not statically bound |

## P077 apps/web/src/app/media/media-details.component.ts

Routes: /media/:id

Headings: Media details; {{ value.safe_filename }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to library | a | Not statically bound |
| {{ value.status === 'archived' ? 'Restore' : 'Archive' }} | button | Not statically bound |

## P078 apps/web/src/app/publishing/publishing-dashboard.component.ts

Routes: /publishing

Headings: Mock Publishing; Active Brand; Connector; Active destinations; Approved, unpublished; Successful; Failed / retryable; Recent executions

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Publish approved content | a | Not statically bound |
| Create destination | a | Not statically bound |
| Manage Brands | a | Not statically bound |
| View all history | a | Not statically bound |
| {{ item.content_snapshot['product_name'] }} · {{ item.id.slice(0, 8) }} | a | Not statically bound |

## P079 apps/web/src/app/publishing/destination-list.component.ts

Routes: /publishing/destinations

Headings: Publishing destinations; No destinations found

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create destination | a | Not statically bound |
| Apply filters | button | Not statically bound |
| View | a | Not statically bound |
| Edit | a | Not statically bound |
| Disable | button | Not statically bound |
| Enable | button | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P080 apps/web/src/app/publishing/destination-form.component.ts

Routes: /publishing/destinations/new, /publishing/destinations/:id/edit

Headings: {{ editing() ? 'Edit' : 'Create' }} publishing destination

Disclosures: Development testing

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Search | button | Not statically bound |
| Refresh | button | Not statically bound |
| Search | button | Not statically bound |
| Refresh | button | Not statically bound |
| Refresh authors | button | Not statically bound |
| Configure WordPress credentials | a | Not statically bound |
| Search | button | Not statically bound |
| Refresh | button | Not statically bound |
| Refresh publications | button | Not statically bound |
| Configure Shopify credentials | a | Not statically bound |
| {{ busy() ? 'Saving…' : 'Save destination' }} | button | Yes; runtime evaluation unverified |
| Cancel | a | Not statically bound |

## P081 apps/web/src/app/publishing/destination-details.component.ts

Routes: /publishing/destinations/:id

Headings: Destination details; {{ value.name }}; Recent executions

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to destinations | a | Not statically bound |
| Edit | a | Not statically bound |
| Disable | button | Not statically bound |
| Enable | button | Not statically bound |
| Publish approved content here | a | Not statically bound |
| {{ execution.content_snapshot['product_name'] }} · {{ execution.id.slice(0, 8) }} | a | Not statically bound |

## P082 apps/web/src/app/publishing/publish-new.component.ts

Routes: /publishing/new

Headings: Publish approved content; WordPress mapped preview; Original generated text; Sanitized WordPress output; Shopify mapped preview; Original generated text; Sanitized Shopify description

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Upload a new image | a | Not statically bound |
| Upload a new image | a | Not statically bound |
| Remove value | button | Not statically bound |
| Add value | button | Not statically bound |
| Remove option | button | Not statically bound |
| Add option | button | Yes; runtime evaluation unverified |
| Generate variant matrix | button | Not statically bound |
| Remove variant | button | Not statically bound |
| Add structured variant | button | Not statically bound |
| Generate content | a | Not statically bound |
| Create destination | a | Not statically bound |
| {{ busy() ? 'Publishing…' : 'Run publishing action' }} | button | Yes; runtime evaluation unverified |

## P083 apps/web/src/app/publishing/execution-list.component.ts

Routes: /publishing/executions

Headings: Publishing execution history; No executions found

Disclosures: Advanced

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Publish content | a | Not statically bound |
| Apply | button | Not statically bound |
| Reset | button | Not statically bound |
| View details | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P084 apps/web/src/app/publishing/execution-details.component.ts

Routes: /publishing/executions/:id

Headings: Publishing execution; {{ value.status }}; Shopify media processing; Remote drift comparison; Explicit assignment resolution; Content snapshot; Key features; SEO and social; Attempt timeline

Disclosures: Show complete immutable snapshot

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to history | a | Not statically bound |
| {{ busy() ? 'Retrying…' : 'Retry original snapshot' }} | button | Yes; runtime evaluation unverified |
| Refresh remote state | button | Yes; runtime evaluation unverified |
| View Product | a | Not statically bound |
| View source Artifact | a | Not statically bound |
| View destination | a | Not statically bound |
| Move remote post to draft | button | Yes; runtime evaluation unverified |
| Keep remote changes | button | Yes; runtime evaluation unverified |
| Update remote from approved Artifact | button | Yes; runtime evaluation unverified |
| Create a new draft | a | Not statically bound |
| Open destination settings | a | Not statically bound |
| Review collection removal | button | Yes; runtime evaluation unverified |
| Review publication removal | button | Yes; runtime evaluation unverified |
| Confirm selected removal | button | Yes; runtime evaluation unverified |

## P085 apps/web/src/app/publishing/schedules.component.ts

Routes: /publishing/schedules, /publishing/schedules/new

Headings: Schedules; Schedule approved content; Next occurrences

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Preview occurrences | button | Not statically bound |
| Create schedule | button | Yes; runtime evaluation unverified |
| Resume | button | Not statically bound |
| Pause | button | Not statically bound |
| Details | a | Not statically bound |

## P086 apps/web/src/app/publishing/schedule-details.component.ts

Routes: /publishing/schedules/:id

Headings: {{ schedule()?.name \|\| 'Schedule' }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| View jobs | a | Not statically bound |

## P087 apps/web/src/app/publishing/jobs.component.ts

Routes: /publishing/jobs

Headings: Jobs

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Timeline | a | Not statically bound |
| Retry | button | Not statically bound |
| Cancel | button | Not statically bound |

## P088 apps/web/src/app/publishing/job-details.component.ts

Routes: /publishing/jobs/:id

Headings: Execution timeline; Attempt {{ item.attempt_number }} · {{ item.outcome }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Schedule | a | Not statically bound |
| Product | a | Not statically bound |
| Artifact v{{ value.artifact_version }} | a | Not statically bound |
| Publishing execution | a | Not statically bound |

## P089 apps/web/src/app/publishing/workers.component.ts

Routes: /operations/workers

Headings: Publishing workers

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ item.worker_id }} | a | Not statically bound |

## P090 apps/web/src/app/publishing/worker-details.component.ts

Routes: /operations/workers/:id

Headings: {{ worker()?.worker_id \|\| 'Worker' }}; Recent leased jobs

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ job.requested_action }} · {{ job.state }} | a | Not statically bound |

## P091 apps/web/src/app/workflows/workflow-list.component.ts

Routes: /workflows

Headings: Workflows; No active Brand; Total; Waiting approval; Completed; Failed / retryable; No Workflows found

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create Workflow | a | Not statically bound |
| Manage Brands | a | Not statically bound |
| Apply | button | Not statically bound |
| Reset | button | Not statically bound |
| View | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P092 apps/web/src/app/workflows/workflow-new.component.ts

Routes: /workflows/new

Headings: Create Product Content Workflow; Three durable steps

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create Product | a | Not statically bound |
| Create destination | a | Not statically bound |
| {{ busy() ? 'Starting…' : 'Create and start' }} | button | Yes; runtime evaluation unverified |
| Cancel | a | Not statically bound |

## P093 apps/web/src/app/workflows/workflow-details.component.ts

Routes: /workflows/:id

Headings: Workflow {{ id.slice(0, 8) }}; Current state; Human approval required; Step attempts

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| ← Workflows | a | Not statically bound |
| Refresh | button | Yes; runtime evaluation unverified |
| {{ item.brand_name }} | a | Not statically bound |
| {{ item.product_name }} | a | Not statically bound |
| {{ item.destination_name }} | a | Not statically bound |
| Start | button | Yes; runtime evaluation unverified |
| Review Artifact | a | Not statically bound |
| Continue after review | button | Yes; runtime evaluation unverified |
| Retry failed step | button | Yes; runtime evaluation unverified |
| Cancel Workflow | button | Yes; runtime evaluation unverified |

## P094 apps/web/src/app/operations/approvals.component.ts

Routes: /approvals

Headings: Approvals

Disclosures: None found

Dialogs: 0; tables: 1.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ tab.label }} | a | Not statically bound |
| Apply | button | Not statically bound |
| Review | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P095 apps/web/src/app/operations/control-center.component.ts

Routes: /operations, /operations/jobs, /operations/providers, /operations/storage, /operations/security, /operations/releases, /operations/configuration

Headings: Operations Control Center; Needs Your Attention; {{ attentionTitle(alert['code']) }}; Recoverable execution failures; Durable work by runtime state; Next operational window; Execution history; Overall; Workers; Recoverable; Backups; Storage; Security; System health; Durable jobs; Provider registry

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Overview | a | Not statically bound |
| Health | a | Not statically bound |
| Jobs | a | Not statically bound |
| Recovery | a | Not statically bound |
| Providers | a | Not statically bound |
| Backups | a | Not statically bound |
| Storage | a | Not statically bound |
| Security | a | Not statically bound |
| Audit | a | Not statically bound |
| Release readiness | a | Not statically bound |
| Open Recovery Center | a | Not statically bound |
| Review issue | a | Not statically bound |
| Review recovery | a | Not statically bound |
| Open advanced Job Explorer | a | Not statically bound |
| Open Calendar | a | Not statically bound |
| Open schedules | a | Not statically bound |
| Open execution history | a | Not statically bound |
| Open Job Explorer | a | Not statically bound |

## P096 apps/web/src/app/operations/health.component.ts

Routes: /operations/health

Headings: Operational health; {{ item.component }}; Release; Scheduler and workers; Campaigns

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Refresh | button | Not statically bound |
| Review jobs | a | Not statically bound |
| Review workers | a | Not statically bound |
| Review Campaigns | a | Not statically bound |
| Open Content Calendar | a | Not statically bound |

## P097 apps/web/src/app/operations/recovery.component.ts

Routes: /operations/recovery

Headings: Failure Recovery Center; No recoverable failures; {{ item.category }} · {{ item.product_name \|\| item.entity_type }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Open catch-up Activity | a | Not statically bound |
| Open details and available actions | a | Not statically bound |

## P098 apps/web/src/app/operations/backups.component.ts

Routes: /operations/backups

Headings: Backups; Backup habit; No backups; {{ item.backup_key }}; Restore preflight

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Create full backup | button | Yes; runtime evaluation unverified |
| Verify | button | Yes; runtime evaluation unverified |
| Restore preflight | button | Yes; runtime evaluation unverified |

## P099 apps/web/src/app/operations/execution-history.component.ts

Routes: /operations/audit, /execution-history

Headings: Execution History

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Export filtered CSV | button | Not statically bound |
| Apply | button | Not statically bound |
| {{ timeline() ? 'List view' : 'Timeline view' }} | button | Not statically bound |
| Open related record | a | Not statically bound |
| Previous | button | Yes; runtime evaluation unverified |
| Next | button | Yes; runtime evaluation unverified |

## P100 apps/web/src/app/operations/provider-settings.component.ts

Routes: /settings/providers

Headings: Provider integrations; {{ provider.display_name }}

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to settings | a | Not statically bound |

## P101 apps/web/src/app/operations/settings.component.ts

Routes: /settings, /settings/:section

Headings: Settings; Owner profile; Preferences; Change password; Sessions; System diagnostics

Disclosures: None found

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| {{ x[0] }} | a | Not statically bound |
| Save profile | button | Yes; runtime evaluation unverified |
| Configure OpenAI-compatible provider | a | Not statically bound |
| Save preferences | button | Yes; runtime evaluation unverified |
| Change password | button | Yes; runtime evaluation unverified |
| Sign out other sessions | button | Not statically bound |
| Sign out all sessions | button | Not statically bound |

## P102 apps/web/src/app/intelligence/supplier-shortlisting.component.ts

Routes: /intelligence/supplier-shortlisting

Headings: Supplier Shortlisting; {{ context.product \|\| 'Selected product' }}; Shortlisting Overview; Context; Shortlist; {{ item['supplier'] \|\| 'Supplier' }}; Next step; Safety and readiness

Disclosures: Advanced context evaluation; View shortlist details

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Evaluate current shortlist | button | Yes; runtime evaluation unverified |
| Evaluate shortlist | button | Yes; runtime evaluation unverified |
| Assess this supplier's evidence | a | Not statically bound |
| Shortlist for verification | button | Yes; runtime evaluation unverified |
| Find suppliers | a | Not statically bound |
| Verify shortlisted suppliers | a | Not statically bound |
| Compare suppliers | a | Not statically bound |
| Compare sourcing scenarios | a | Not statically bound |

## P103 apps/web/src/app/intelligence/supplier-portfolio-workspace.component.ts

Routes: /intelligence/supplier-portfolios/:portfolioId, /intelligence/supplier-portfolios

Headings: Supplier portfolios; Portfolio list; {{ portfolio()?.name }}; Overview; Suppliers & exposure; Concentration; Dependencies; {{ text(finding, 'dependency_type') }}; Alternate readiness; {{ text(item, 'readiness_state', 'UNKNOWN') }}; Resilience dimensions; {{ dimensionLabel(dimension.dimension) }}; Recommendations; {{ recommendation.recommendation_type }}; Disruption simulations; {{ simulation.simulation_type }}; BASELINE; SIMULATED; DELTA; Assessment history; Operational state; Report view; Executive Summary; Methodology / versions; Limitations; {{ actionLabel(pendingAction()) }}

Disclosures: None found

Dialogs: 1; tables: 3.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Operations | a | Not statically bound |
| Refresh | button | Yes; runtime evaluation unverified |
| Open workspace | a | Not statically bound |
| {{ actionLabel(action) }} | button | Not statically bound |
| {{ simulationBusy() ? 'Creating...' : 'Create simulation' }} | button | Yes; runtime evaluation unverified |
| Open Operations Control Center | a | Not statically bound |
| Open Recovery Center | a | Not statically bound |
| Print report | button | Not statically bound |
| {{ actionBusy() ? 'Submitting...' : 'Confirm action' }} | button | Yes; runtime evaluation unverified |
| Cancel | button | Not statically bound |

## P104 apps/web/src/app/intelligence/cross-marketplace-supplier.component.ts

Routes: /intelligence/cross-marketplace

Headings: Cross-marketplace Supplier Intelligence; {{ context.product \|\| 'Selected product' }}; Overview; Suppliers for {{ productContext()?.product \|\| 'the selected product' }}; {{ supplier.display_name }}; Compare selected suppliers; {{ selected()?.display_name }}; Product match; Where VAYUJIT found them; Verification readiness; Risk and important unknowns; Commercial information; Sources; Commercial Intelligence; Verification / certifications; Capabilities / facilities; Risk / contradictions; Confidence explanation; Comparison; Reports and history

Disclosures: Already know a supplier?; Advanced: unscoped supplier records (not canonical journey results); Advanced technical details; View source metadata; View commercial fields; View verification fields; View capability fields; View risk and contradiction fields; View confidence fields; Advanced research controls; View server report

Dialogs: 0; tables: 0.

| Exact source action text | Kind | Disabled condition present |
| --- | --- | --- |
| Back to Intelligence | a | Not statically bound |
| Record a supplier manually | a | Not statically bound |
| {{ researchBusy() ? 'Finding suppliers...' : 'Find suppliers for this product' }} | button | Yes; runtime evaluation unverified |
| Review product opportunities | a | Not statically bound |
| {{ tab }} | a | Not statically bound |
| Reconcile accepted evidence | button | Yes; runtime evaluation unverified |
| Refresh | button | Not statically bound |
| Review product opportunities | a | Not statically bound |
| Inspect {{ supplier.display_name }} | button | Not statically bound |
| Research again | button | Yes; runtime evaluation unverified |
| View supplier | button | Not statically bound |
| Shortlist suppliers | a | Not statically bound |
| Compare selected ({{ comparisonSelection().size }}) | button | Yes; runtime evaluation unverified |
| Shortlist this supplier | a | Not statically bound |
| Continue to sourcing economics | a | Not statically bound |
| Prepare local requirements and record quotes | a | Not statically bound |
| Evaluate ranking | button | Not statically bound |
| Generate report | button | Not statically bound |
| Prepare internal sourcing handoff | button | Not statically bound |
| Compare selected ({{ comparisonSelection().size }}) | button | Yes; runtime evaluation unverified |
