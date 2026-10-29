# Enterprise Core Banking & Ledger Platform

## Architecture Focus
Backend Enterprise Microservices (Java / Spring Boot / Event-Driven)

## Executive Summary

We need a high-concurrency, auditable Core Banking and Financial Settlement platform named **Apex Ledger**. Designed for retail and commercial financial operations, the system handles account lifecycle management, double-entry general ledger accounting, real-time transaction processing, automated compliance/AML (Anti-Money Laundering) screening, and foreign currency exchange (FX) settlement.

---

## Strategic Capabilities & Core Domains

### 1. Account Lifecycle & Deposit Management (`Accounts`)

**Business Capability:**
Manages the onboarding, maintenance, overdraft limits, and state lifecycles of Customer Deposit Accounts (Savings, Checking, High-Yield) and Commercial Accounts.

**Business Rules & Invariants:**
- An Account must belong to a verified Customer profile before opening.
- Account Status transitions: `PROVISIONAL` -> `ACTIVE` -> `FROZEN` -> `TERMINATED`.
- Accounts in `FROZEN` state cannot originate outgoing debit transfers but can accept incoming credit transfers.
- Overdraft limits must be individually approved based on customer risk tier and cannot exceed defined regulatory caps.
- An account cannot be closed (`TERMINATED`) if it holds a non-zero balance or has pending un-settled holds.

**Ubiquitous Language:**
- `Account Number` (IBAN/Internal Format)
- `Deposit Account`
- `Hold` / `Lien`
- `Overdraft Boundary`
- `Account State`

---

### 2. Double-Entry General Ledger (`General Ledger`)

**Business Capability:**
Maintains the immutable financial truth of the bank using strict multi-currency double-entry bookkeeping rules. Serves as the authoritative source of truth for bank liabilities, assets, equity, revenues, and expenses.

**Business Rules & Invariants:**
- **Zero-Sum Ledger Rule:** Every financial transaction must consist of balanced journal entries where `Total Debits == Total Credits`.
- Ledger Entries are strictly **immutable**. Corrections must be executed exclusively via reversing journal entries (`Adjustment Journal`).
- Posting to a closed accounting Period (`Fiscal Period`) is strictly forbidden.
- Real-time balance calculations must separate `Book Balance` (settled funds) from `Available Balance` (book balance minus active holds).

**Ubiquitous Language:**
- `Chart of Accounts` (Assets, Liabilities, Equity, Expense, Income)
- `Journal Entry`
- `Debit` / `Credit`
- `Book Balance`
- `Available Balance`
- `Fiscal Period`

---

### 3. Payment Processing & Money Transfer (`Payments`)

**Business Capability:**
Orchestrates domestic transfers, instant peer-to-peer payments, and cross-border wire transfers across internal accounts and external clearing networks (e.g., SWIFT, ACH).

**Business Rules & Invariants:**
- Prior to initiating an outgoing transfer, the system must request a balance reservation (`Hold`) from the `Accounts` context.
- Payment execution follows a two-phase flow: **Authorization** (holds funds) -> **Settlement** (posts ledger entry and releases hold).
- If payment processing fails at external clearing networks, the reserved hold must be automatically released (`Reversal`).
- All cross-border transactions above $10,000 USD equivalent require explicit foreign exchange settlement and AML risk clearance prior to execution.

**Ubiquitous Language:**
- `Payment Order`
- `Transfer Direction` (Inbound / Outbound / Internal)
- `Clearing Network` (ACH, SWIFT, SEPA)
- `Settlement Batch`
- `Reservation Hold`

---

### 4. Foreign Exchange & Multi-Currency Settlement (`Treasury & FX`)

**Business Capability:**
Provides live FX rate quotes, currency conversion execution, and manages multi-currency balance clearing for international payment routes.

**Business Rules & Invariants:**
- An FX Quote is locked for a maximum of 30 seconds (`Rate Hold Expiry`).
- Settlements occurring in foreign currency must record both the local currency amount, target foreign amount, and the exact exchange rate index used at execution time.
- Currency conversion operations must publish rate utilization metrics to ensure treasury positions stay hedged.

**Ubiquitous Language:**
- `Currency Pair`
- `Exchange Rate Quote`
- `Spread Rate`
- `Rate Lock Expiry`
- `Treasury Clearing`

---

### 5. Compliance, AML & Transaction Screening (`Compliance & Risk`)

**Business Capability:**
Screen real-time transactions and account operations against sanctioned watchlists (OFAC), PEP (Politically Exposed Persons) lists, and anomalous velocity patterns.

**Business Rules & Invariants:**
- Every high-value transaction (>$5,000 USD or cross-border) must undergo real-time Sanction Screening before payment authorization completes.
- If a transaction triggers a compliance match, the system must issue a `Compliance Hold` on the transaction, notify the Risk Operations Queue, and publish a `TransactionSuspended` event.
- Compliance overrides (`Approval` or `Rejection`) must be logged with operator ID, regulatory justification, and cryptographic audit timestamp.

**Ubiquitous Language:**
- `Sanctions List` (OFAC, UN)
- `PEP Screening`
- `Transaction Velocity`
- `Compliance Hold`
- `SAR` (Suspicious Activity Report)

---

## End-to-End Business Processes

### Flow A: Cross-Border Outbound Payment Execution

1. **Initiation:** Customer requests a $15,000 USD transfer from a Local Currency Deposit Account to an overseas recipient via SWIFT.
2. **Screening Check:** `Payments` context routes payment payload to `Compliance & Risk` for Sanctions and AML screening.
3. **FX Lock:** `Payments` requests a 30-second locked FX quote from `Treasury & FX`.
4. **Fund Reservation:** `Payments` requests `Accounts` to place a `Hold` for the local equivalent total amount.
5. **Ledger Posting:** `General Ledger` records a pending journal entry reserving liabilities.
6. **Clearing Dispatch:** `Payments` dispatches the transfer to the SWIFT clearing gateway.
7. **Settlement Confirmation:** Upon clearing acknowledgement, `Payments` notifies `Accounts` to release the hold and convert it to a permanent debit, while `General Ledger` posts the finalized zero-sum journal entry.

---

## System Events Output Summary

The system relies on domain event emissions to maintain eventual consistency across bounded contexts:

- `AccountCreatedEvent` (Published by `Accounts`, consumed by `Compliance`)
- `AccountFrozenEvent` (Published by `Accounts`, consumed by `Payments`)
- `PaymentRequestedEvent` (Published by `Payments`, consumed by `Compliance`)
- `ComplianceClearedEvent` / `ComplianceFlaggedEvent` (Published by `Compliance`, consumed by `Payments`)
- `FundsReservedEvent` / `FundsReleasedEvent` (Published by `Accounts`, consumed by `Payments` & `General Ledger`)
- `JournalPostedEvent` (Published by `General Ledger`, consumed by `Reporting`)