# 3 minute 30 second Demo Script

## 0:00-0:20 - Problem

"Industrial teams lose critical time searching across maintenance records, inspection reports, manuals and safety procedures. Worse, a decision made from only one document can miss the history that explains an asset failure."

## 0:20-0:40 - Solution

"IndusMind AI turns fragmented industrial documents into an evidence-backed operational brain. It connects asset history, answers questions with citations and creates a traceable root-cause investigation brief."

## 0:40-1:05 - Login and command center

Sign in with the administrator account. Show the dashboard, indexed-document count, connected assets and AI-service status.

"The application uses role-based JWT security. The command center shows corpus health and recurring patterns discovered across records."

## 1:05-1:35 - Upload

Open Knowledge Library and upload `pump-p101-inspection-report.txt`.

"The Spring Boot API stores metadata while FastAPI extracts text, equipment tags, dates, failure modes and measurements. Page-aware chunks are persisted in ChromaDB."

## 1:35-2:15 - Ask a cross-document question

Open AI Copilot and ask: "Why did Pump P-101 fail repeatedly in 2025?"

"The system retrieves evidence across maintenance, inspection and OEM records. With a Gemini key it generates a grounded response; without internet it uses the built-in evidence-summary mode."

Point to confidence, mode and source cards.

## 2:15-2:45 - Asset 360

Open Asset 360 and load `P-101`.

"Asset 360 connects failure signals, measurements and dated evidence into one equipment history instead of forcing an engineer to reconstruct it manually."

## 2:45-3:12 - RCA

Open RCA Intelligence and generate the P-101 report.

"The RCA brief separates observed failure evidence from probable contributors, recommended checks and preventive actions. Every conclusion preserves the source trail and carries an engineering-verification disclaimer."

## 3:12-3:30 - Close

"IndusMind AI reduces search time, preserves operational knowledge and helps teams make faster, safer maintenance decisions. Its modular React, Spring Boot, FastAPI, PostgreSQL and ChromaDB architecture can scale from a local plant prototype to enterprise document intelligence."

