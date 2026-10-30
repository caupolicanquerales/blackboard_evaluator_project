# Architecture Plan — Apex Ledger (Enterprise Core Banking & Ledger Platform)

Source: `blackboard/domain-boundary-analysis.json` (+ draft). Stack: Java 21, Spring Boot 3, Maven, single deployable module, event-driven (in-process Spring events), in-memory adapters (persistence technology not specified).

## Bounded contexts
| Context | Responsibility | Core invariants |
|---|---|---|
| Accounts | Deposit account lifecycle, overdraft limits, holds | Verified customer; PROVISIONAL→ACTIVE→FROZEN→TERMINATED; FROZEN cannot debit but accepts credits; overdraft ≤ regulatory cap; no termination with balance or active holds |
| General Ledger | Immutable double-entry truth, balances | Debits == Credits; immutable entries (corrections via Adjustment Journal); no posting to closed Fiscal Period; Book vs Available Balance; FX local/foreign/rate recorded |
| Payments | Payment order lifecycle, clearing, settlement batches | Outgoing needs Hold; Authorization then Settlement; clearing failure releases hold; cross-border > USD 10,000 needs FX + AML clearance |
| Treasury & FX | Quotes, conversion, utilization metrics | Quote lock ≤ 30 s; conversions publish rate utilization |
| Compliance & Risk | Screening, Compliance Hold, overrides | > USD 5,000 or cross-border screened before authorization; match → hold + queue + TransactionSuspended; overrides audited (operator, justification, hash timestamp) |

Context map (upstream → downstream): Accounts→Payments, Accounts→Ledger, Accounts→Compliance (events); Payments→Compliance (PaymentRequestedEvent); Compliance→Payments (cleared/flagged); Ledger↔Payments (posting port); Treasury→Payments (quote port); Treasury→Ledger (rate in journal lines).

## Layout (`com.apexledger.banking`)
```
<context>/domain          aggregates, value objects, events (no framework imports)
<context>/application     use-case services + application/port (outbound ports)
<context>/infrastructure  adapters (repositories, anticorruption adapters, event listeners)
<context>/api             thin REST controllers (package `api` since `interface` is a Java keyword)
```
Contexts: `shared` (Money, DomainEvent, DomainRuleViolationException, EventPublisher, Spring wiring), `accounts`, `ledger`, `treasury`, `compliance`, `payments`. Dependency direction: api → application → domain; infrastructure → application/domain. Cross-context interaction only through published events (listeners) or outbound ports implemented by anticorruption adapters in the consumer's infrastructure layer; application/domain never import another context.

## Build order
1. T0-001 scaffold (pom, main class).
2. Shared kernel (001–006).
3. Accounts domain/app/infra/api (007–014).
4. General Ledger (015–022), then Accounts↔Ledger adapter (023), ledger API (024).
5. Treasury & FX (025–031).
6. Compliance & Risk (032–039).
7. Payments (040–050), then Compliance event listener (051, needs Payment events).

Each unit N yields T1-N (test) → T2-N (code, also waits for prerequisite units' T2) → T3-N (refactor).

## Bounded context → units of work
- Shared: 001 Money, 002 DomainRuleViolationException, 003 DomainEvent, 004 EventPublisher, 005 SpringEventPublisher, 006 BankingConfiguration.
- Accounts: 007 AccountEvents, 008 AccountState, 009 Hold, 010 DepositAccount, 011 AccountService, 012 InMemoryAccountRepository, 013 ConfigurableCustomerVerificationAdapter, 014 AccountController, 023 LedgerBalanceAdapter.
- General Ledger: 015 LedgerEvents, 016 ChartOfAccounts, 017 FiscalPeriod, 018 JournalEntry, 019 BalanceCalculator, 020 GeneralLedgerService, 021 InMemoryLedgerStore, 022 LedgerHoldEventListener, 024 GeneralLedgerController.
- Treasury & FX: 025 CurrencyPair, 026 ExchangeRateQuote, 027 TreasuryEvents, 028 FxService, 029 InMemoryQuoteRepository, 030 StubFxRateProviderAdapter, 031 FxController.
- Compliance & Risk: 032 ComplianceEvents, 033 ScreeningPolicy, 034 ComplianceHold, 035 OverrideRecord, 036 ComplianceService, 037 InMemoryComplianceStore, 038 StubSanctionsScreeningAdapter, 039 ComplianceController, 051 ComplianceEventListener.
- Payments: 040 PaymentEvents, 041 PaymentOrder, 042 SettlementBatch, 043 PaymentService, 044 InMemoryPaymentOrderRepository, 045 SimulatedClearingNetworkAdapter, 046 AccountsHoldAdapter, 047 TreasuryQuoteAdapter, 048 LedgerPostingAdapter, 049 PaymentsEventListener, 050 PaymentController.

## Decisions / assumptions
- Account state transitions additionally allow FROZEN→ACTIVE (unfreeze) and ACTIVE/FROZEN→TERMINATED; TERMINATED is terminal.
- Compliance call is asynchronous via events; Payments stays SUSPENDED/FUNDS_RESERVED until a verdict.
- Treasury event name (`RateUtilizationRecordedEvent`) and Customer verification (property-driven adapter) are architecture choices for open questions.
- Available Balance stays in General Ledger, fed by hold events; Accounts reads it via `LedgerBalancePort`.
- Pending-journal-on-reservation is not modeled; ledger posts only at settlement (preserves immutability).

## Risks
Name collisions (Hold / Compliance Hold / Reservation Hold; Reversal / Adjustment Journal); in-process events give no durability (swap adapters for a broker later); in-memory stores are not persistent; Payments is downstream of four contexts and must stay orchestration-only.
