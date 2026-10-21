"""Write the frozen treasury question set from source passages.

Questions were written by reading passages directly (not retriever output).
Every gold quote must be verbatim in its passage; alternates are any passage
in the scoped filing that also states the answer key. Run once, review, freeze.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACC = {'MSTR-K': '0001050446-26-000020', 'MSTR-Q': '0001050446-26-000044', 'BMNR-K': '0001493152-25-024679',
       'BMNR-Q': '0001628280-26-048157', 'COIN-K': '0001679788-26-000015', 'COIN-Q': '0001679788-26-000088'}
NOTE = 'Author-written by the Claude Code agent from source passages before any generator run; not independently human verified.'

# (id, filing, question, quote (verbatim), answer key regex for alternates, reference answer)
ANSWERABLE = {
 'heldout': [
  ('t01', 'BMNR-K', 'How many people did BitMine employ at the end of fiscal 2025, and how many contractors did it engage?', 'As of August 31, 2025, we employed three individuals (Chief Executive Officer, Chief Financial Officer, and President) and engaged four dedicated contractors.', r'employed three individuals', 'Three employees (CEO, CFO and President) and four dedicated contractors.'),
  ('t02', 'BMNR-K', 'How much cash did BitMine use to buy ether in its fiscal year ended August 31, 2025?', 'The increase in investing cash outflow was almost entirely driven by the $7,433,131 purchase of ETH.', r'7,433,131', '$7,433,131 thousand (about $7.43 billion) of ETH purchases.'),
  ('t03', 'BMNR-K', 'What revenue did BitMine report for fiscal 2025 versus fiscal 2024?', 'During the fiscal year ended August 31, 2025, revenues were $6,095, compared to $3,310 during the fiscal year ended August 31, 2024.', r'revenues were \$6,095', '$6,095 thousand in fiscal 2025 versus $3,310 thousand in fiscal 2024.'),
  ('t04', 'BMNR-K', 'Up to what dollar amount of common stock could BitMine sell under the at-the-market program it set up in July 2025?', 'permitting sales of up to $20,000,000 of our common stock from time to time', r'\$20,000,000', 'Up to $20,000,000 of common stock.'),
  ('t05', 'BMNR-K', 'Who was appointed chairman of the BitMine board in June 2025?', 'In June 2025, we expanded our board of directors (the “Board”) leadership by appointing Thomas J. Lee, a leader in financial investments and treasury strategies, as Chairman.', r'Thomas J\. Lee', 'Thomas J. Lee.'),
  ('t06', 'BMNR-Q', 'How much revenue did BitMine earn from staking and validation in the quarter ended May 31, 2026?', 'During the three months ended May 31, 2026, revenue from staking and validation was $45,743, compared to $0 in the three months ended May 31, 2025.', r'staking and validation was \$45,743', '$45,743 thousand, versus $0 a year earlier.'),
  ('t07', 'BMNR-Q', 'Who did BitMine hire as its chief financial officer, and on what date was that employment agreement signed?', 'on January 7, 2026, the Company entered into an employment agreement with Young Kim to serve as the Company’s Chief Financial Officer and Chief Operating Officer.', r'Young Kim', 'Young Kim, under an employment agreement dated January 7, 2026 (CFO and COO).'),
  ('t08', 'BMNR-Q', 'Why did BitMine record no miner leasing revenue in the quarter ended May 31, 2026?', 'The machine lease agreements expired on December 31, 2025 and were not renewed.', r'lease agreements expired on December 31, 2025', 'The machine lease agreements expired on December 31, 2025 and were not renewed.'),
  ('t09', 'BMNR-Q', 'How many shares of Series A Preferred Stock did BitMine sell after May 31, 2026, and at what price per share?', 'the Company completed an underwritten public offering of 3,500,000 shares of its Series A Preferred Stock at a public offering price of $80.00 per share', r'3,500,000 shares', '3,500,000 shares at $80.00 per share (net proceeds $273.8 million).'),
  ('t10', 'BMNR-Q', 'How much ether did BitMine hold as of May 31, 2026, and what was it worth?', 'As of May 31, 2026, the Company held 5,416,945 ETH with a fair value of $10.9 billion', r'5,416,945 ETH', '5,416,945 ETH with a fair value of $10.9 billion.'),
  ('t11', 'MSTR-K', 'How many bitcoins did Strategy hold as of February 13, 2026, and what was the average purchase price?', 'As of February 13, 2026, we held approximately 717,131 bitcoins that were acquired at an aggregate purchase price of $54.5 billion and an average purchase price of approximately $76,027 per bitcoin, inclusive of fees and expenses.', r'\$76,027', 'About 717,131 bitcoins at an average of about $76,027 each ($54.5 billion aggregate).'),
  ('t12', 'MSTR-K', 'Which firms act as custodians for Strategy\'s bitcoin?', 'Our current custodians are Anchorage Digital Bank N.A. (“Anchorage”), Coinbase Custody Trust Company, LLC (“Coinbase”), and Fidelity Digital Assets, NA (f/k/a Fidelity Digital Asset Services, LLC) (“Fidelity”).', r'Our current custodians are Anchorage', 'Anchorage Digital Bank, Coinbase Custody Trust Company and Fidelity Digital Assets.'),
  ('t13', 'MSTR-K', 'What was the balance of Strategy\'s USD Reserve in February 2026, and what is the reserve meant to fund?', 'As of February 13, 2026, the balance of the USD Reserve was $2.25 billion', r'USD Reserve was \$2\.25 billion', '$2.25 billion, to support preferred stock dividends and interest on outstanding debt.'),
  ('t14', 'MSTR-K', 'How many employees did Strategy have at the end of 2025, and how many of them worked outside the United States?', 'As of December 31, 2025, we had a total of 1,539 employees, of whom 448 were based in the United States and 1,091 were based internationally.', r'1,539 employees', '1,539 employees in total, of whom 1,091 were international (448 in the U.S.).'),
  ('t15', 'MSTR-K', 'When does full support end for Strategy\'s on-premises software licenses?', 'with full support for such licenses ending December 31, 2026', r'full support for such licenses ending', 'December 31, 2026.'),
  ('t16', 'MSTR-Q', 'How many bitcoins did Strategy hold on July 24, 2026, and what was their market value?', 'As of July 24, 2026, we held approximately 843,775 bitcoins, which had an aggregate market value of $54.14 billion', r'843,775', 'About 843,775 bitcoins worth $54.14 billion.'),
  ('t17', 'MSTR-Q', 'What BTC Yield did Strategy report for the second quarter of 2026?', 'We achieved BTC Yield of 5.0% and 8.1% for the three and six months ended June 30, 2026, respectively', r'BTC Yield of 5\.0%', '5.0% for the quarter (8.1% for the six months).'),
  ('t18', 'MSTR-Q', 'How much principal of its 2029 convertible notes did Strategy buy back in the June 2026 quarter, and what did it pay?', 'we repurchased $1.50 billion aggregate principal amount of our 0% Convertible Senior Notes due 2029 in privately negotiated transactions, for an aggregate cash repurchase price of $1.38 billion', r'cash repurchase price of \$1\.38 billion', '$1.50 billion of principal for $1.38 billion in cash.'),
  ('t19', 'MSTR-Q', 'What were Strategy\'s total revenues for the three months ended June 30, 2026?', 'Total revenues were $122.4 million and $246.7 million for the three and six months ended June 30, 2026, respectively', r'\$122\.4 million', '$122.4 million.'),
  ('t20', 'MSTR-Q', 'How large was the new MSTR common stock offering Strategy announced on March 23, 2026?', 'On March 23, 2026, we announced a new $21.0 billion offering of MSTR Stock (the “MSTR Increase”).', r'\$21\.0 billion offering', '$21.0 billion.'),
  ('t21', 'COIN-K', 'What was Coinbase\'s headcount at December 31, 2025?', 'As of December 31, 2025, we had 4,951 employees.', r'4,951 employees', '4,951 employees.'),
  ('t22', 'COIN-K', 'How many exchanges does Coinbase operate, and what are they called?', 'We currently operate four exchanges: the Coinbase Exchange, the Coinbase International Exchange, the Coinbase Derivatives Exchange, and the Deribit Exchange.', r'operate four exchanges', 'Four: Coinbase Exchange, Coinbase International Exchange, Coinbase Derivatives Exchange and Deribit Exchange.'),
  ('t23', 'COIN-K', 'Which assets could U.S. consumers stake through Coinbase at the end of 2025?', 'we support eight staking assets through our platform for consumers as of December 31, 2025: Cardano (ADA), Avalanche (AVAX), Cosmos (ATOM), Polkadot (DOT), Ethereum (ETH), MATIC (POL), Solana (SOL), and Tezos (XTZ).', r'eight staking assets', 'Eight: ADA, AVAX, ATOM, DOT, ETH, POL, SOL and XTZ (subject to jurisdiction).'),
  ('t24', 'COIN-K', 'What is the most Coinbase aims to keep in hot wallets as a share of assets under custody?', 'generally seek to hold no more than 2% of assets under custody in hot wallets at any given time', r'no more than 2% of assets under custody', 'No more than 2% of assets under custody.'),
  ('t25', 'COIN-K', 'When and where was Coinbase, Inc. first incorporated?', 'We were initially incorporated in May 2012 as Coinbase, Inc., a Delaware corporation.', r'initially incorporated in May 2012', 'May 2012, as a Delaware corporation.'),
  ('t26', 'COIN-Q', 'What were Coinbase\'s assets on platform at June 30, 2026, and what drove the decline from a year earlier?', 'Assets on Platform (“AOP”) were $245.9 billion and $425.0 billion at June 30, 2026 and 2025, respectively. The decrease in AOP primarily reflects a $196.5 billion decline driven primarily by the decline in prices of certain crypto assets held on our platform', r'\$245\.9 billion', '$245.9 billion (down from $425.0 billion), driven mainly by lower crypto asset prices.'),
  ('t27', 'COIN-Q', 'How many monthly transacting users did Coinbase have in the quarter ended June 30, 2026?', 'For the three and six months ended June 30, 2026, Monthly Transacting Users (“MTUs”) were 7.6 million and 7.9 million.', r'MTUs”\) were 7\.6 million', '7.6 million for the quarter.'),
  ('t28', 'COIN-Q', 'How much did Coinbase record in restructuring expenses in the second quarter of 2026?', 'For both the three and six months ended June 30, 2026, restructuring expenses were $52.4 million, related to the Restructuring.', r'\$52\.4 million', '$52.4 million.'),
  ('t29', 'COIN-Q', 'How much capacity was left under Coinbase\'s share and debt repurchase program at June 30, 2026?', 'As of June 30, 2026, approximately $2.0 billion remained available', r'\$2\.0 billion remained available', 'About $2.0 billion of the $4.0 billion authorization.'),
  ('t30', 'COIN-Q', 'What percentage of Coinbase\'s total revenue was generated in the U.S. in the June 2026 quarter?', 'For the three and six months ended June 30, 2026, we generated 85% and 84% of total revenue in the U.S.', r'85% and 84% of total revenue', '85% for the quarter (84% for six months).'),
 ],
 'dev': [
  ('d01', 'BMNR-K', 'How much bitcoin did BitMine buy with its June 2025 offering proceeds?', 'purchasing approximately 154.167 BTC', r'154\.167', 'About 154.167 BTC.'),
  ('d02', 'BMNR-Q', 'How much goodwill had BitMine recorded as of May 31, 2026?', 'As of May 31, 2026, the Company recorded goodwill of $15.0 million', r'goodwill of \$15\.0 million', '$15.0 million.'),
  ('d03', 'MSTR-K', 'What BTC Yield did Strategy achieve for 2025?', 'We achieved BTC Yield of 22.8% for the year ended December 31, 2025', r'BTC Yield of 22\.8%', '22.8%.'),
  ('d04', 'MSTR-Q', 'How many bitcoins did Strategy acquire in the quarter ended June 30, 2026?', 'During the three months ended June 30, 2026, we acquired 85,296 bitcoin', r'acquired 85,296 bitcoin', '85,296 bitcoins.'),
  ('d05', 'COIN-K', 'Which company issues USDC?', 'Circle and its affiliate, Circle Internet Financial Europe SAS, are the issuers of USDC', r'issuers of USDC', 'Circle (and its affiliate Circle Internet Financial Europe SAS).'),
  ('d06', 'COIN-Q', 'How much cash, cash equivalents and marketable investments did Coinbase hold at June 30, 2026?', 'cash, cash equivalents, and marketable investments, which totaled $8.8 billion as of June 30, 2026', r'totaled \$8\.8 billion', '$8.8 billion.'),
 ],
}
# Verified by searching the scoped filing's indexed passages: no passage states the answer.
UNANSWERABLE = {
 'heldout': [
  ('u01', 'MSTR-K', 'What price per bitcoin did Strategy pay for purchases made in March 2026?', 'The 10-K covers 2025 and was filed in February 2026; no March 2026 purchases appear.'),
  ('u02', 'MSTR-Q', 'How many customers used Strategy One as of June 30, 2026?', 'No customer count in the indexed narrative.'),
  ('u03', 'MSTR-Q', 'What BTC Yield did Strategy achieve in the third quarter of 2026?', 'The 10-Q ends June 30, 2026.'),
  ('u04', 'BMNR-K', 'How many ETH had BitMine staked as of August 31, 2025?', 'No staked-ETH quantity in the indexed narrative; native staking began later.'),
  ('u05', 'BMNR-Q', 'What was BitMine\'s average cost per ETH for the holdings it owned on May 31, 2026?', 'Holdings and fair value are disclosed, not average cost.'),
  ('u06', 'BMNR-Q', 'How many employees did BitMine have as of May 31, 2026?', 'No headcount in the indexed narrative.'),
  ('u07', 'COIN-K', 'What was Coinbase\'s Adjusted EBITDA for the first quarter of 2026?', 'The 10-K covers 2025; it only gives an expense outlook for Q1 2026.'),
  ('u08', 'COIN-K', 'What purchase price did Coinbase pay to acquire Deribit?', 'No consideration amount in the indexed narrative.'),
  ('u09', 'COIN-Q', 'How many employees were laid off in Coinbase\'s May 2026 restructuring?', 'Restructuring cost is disclosed; no headcount reduction in the indexed narrative.'),
  ('u10', 'COIN-Q', 'What fee percentage does Coinbase charge on a Simple trade?', 'No fee schedule in the indexed narrative.'),
 ],
 'dev': [
  ('v01', 'BMNR-K', 'What staking yield did BitMine earn on its ETH in fiscal 2025?', 'No yield figure.'),
  ('v02', 'COIN-Q', 'What revenue will Coinbase report for the third quarter of 2026?', 'Forecast; not disclosed.'),
  ('v03', 'MSTR-K', 'How many Strategy employees work in Japan?', 'Only U.S./international split is disclosed.'),
 ],
}


def build():
    index = json.loads((ROOT/'corpora/treasury/data/index.json').read_text())
    by_id = {p['passage_id']: p for p in index['passages']}
    tickers = {f: f.split('-')[0] for f in ACC}
    out = {}
    for split in ('heldout', 'dev'):
        rows = []
        for qid, filing, question, quote, key, answer in ANSWERABLE[split]:
            scoped = [p for p in index['passages'] if p['accession'] == ACC[filing]]
            primary = [p for p in scoped if quote in p['text']]
            if len(primary) < 1:
                sys.exit('quote not verbatim in scoped filing: ' + qid)
            alternates = [p for p in scoped if re.search(key, p['text']) and p not in primary]
            gold = [dict(passage_id=p['passage_id'], accession=p['accession'], quote=quote if p in primary else re.search(key, p['text']).group(0)) for p in primary + alternates]
            rows.append(dict(id=qid, split=split, question=question, scope=dict(company=tickers[filing], accessions=[ACC[filing]]), answerable=True, gold=gold, reference_answer=answer, annotation=NOTE))
        for qid, filing, question, why in UNANSWERABLE[split]:
            rows.append(dict(id=qid, split=split, question=question, scope=dict(company=tickers[filing], accessions=[ACC[filing]]), answerable=False, gold=[], reference_answer=None, unanswerable_basis=why, annotation=NOTE))
        for row in rows:
            for g in row['gold']:
                assert g['quote'] in by_id[g['passage_id']]['text']
        out[split] = rows
    return out


if __name__ == '__main__':
    splits = build()
    files = {}
    for split, rows in splits.items():
        path = ROOT/'evaluation/treasury'/(split + '.jsonl')
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(split, len(rows), 'answerable', sum(r['answerable'] for r in rows), 'gold passages', sum(len(r['gold']) for r in rows))
    for f in ('corpora/treasury/data/manifest.json', 'corpora/treasury/data/index.json'):
        files[f] = hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
    freeze = dict(frozen_at=datetime.now(timezone.utc).isoformat(), label_origin=NOTE, human_independent=False,
                  rule='Held-out questions are scored once per configuration; nothing is tuned on them. dev.jsonl is for building.',
                  gold_semantics='Gold passages are alternatives: retrieval counts a hit when any gold passage is in the top k.', files=files)
    (ROOT/'evaluation/treasury/frozen.json').write_text(json.dumps(freeze, indent=2) + '\n')
