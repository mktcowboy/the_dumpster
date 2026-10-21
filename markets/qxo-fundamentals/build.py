#!/usr/bin/env python3
"""Build the standalone QXO fundamentals page, JSON snapshot, SQL dump, and SQLite DB."""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
DATA = ROOT / 'data'
TICKER = 'QXO'
CAPTURED = '2026-10-21'

DATASET_LABELS = {
    'overview': 'Overview metrics',
    'income': 'Income statement',
    'balance': 'Balance sheet',
    'cashflow': 'Cash flow statement',
    'capital_structure': 'Capital structure',
    'working_capital': 'Working capital',
    'growth': 'Growth rates',
    'quarterly': 'Quarterly data',
}


def parse_sections(path):
    sections, name, buf = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith('## '):
            if name:
                sections[name] = '\n'.join(buf).strip()
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if name:
        sections[name] = '\n'.join(buf).strip()
    return sections


def parse_tables(text):
    tables, current = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if current is None:
                current = {'header': cells, 'rows': []}
                tables.append(current)
            elif all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                continue
            else:
                current['rows'].append(cells)
        else:
            current = None
    return tables


def to_number(value):
    s = str(value).strip().replace(',', '').replace('%', '')
    if s in {'', '-', '--', '- -', 'N/A', 'n/a'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def clean_number(value):
    n = to_number(value)
    if n is None:
        return None
    return int(n) if n.is_integer() and abs(n) >= 1 else n


def unit_for(item, dataset=''):
    i = item.lower()
    if 'eps' in i or 'per share' in i or 'per basic share' in i:
        return 'USD/share'
    if '(%)' in item or 'margin' in i or 'return on' in i or 'growth' in dataset:
        return '%'
    if 'ratio' in i or 'net debt to equity' in i or 'price/free cash flow' in i or 'cash flow to net income' in i:
        return 'x'
    if 'number of employees' in i:
        return 'count'
    if 'sales per employee' in i:
        return 'USD/employee'
    if 'cash conversion cycle' in i:
        return 'days'
    if 'shares' in i or 'employees' in i:
        return 'millions'
    if 'market capitalization' in i:
        return 'USD millions'
    return 'USD millions'


def year_period(col):
    col = col.strip()
    m = re.fullmatch(r'(\d{4})\s*Y?', col)
    if m:
        return m.group(1), 'annual', f'{m.group(1)}-12-31'
    if col.upper() == 'TTM':
        return 'TTM', 'ttm', '2026-06-30'
    return None, None, None


def snapshot_period(col):
    mapping = {
        "Dec'25": ('2025-12', 'snapshot', '2025-12-31'),
        "Mar'26": ('2026-03', 'snapshot', '2026-03-31'),
        "Jun'26": ('2026-06', 'snapshot', '2026-06-30'),
    }
    return mapping.get(col.strip(), (col.strip(), 'snapshot', None))


def table_payload(table, skip_rows=()):
    header = [c for c in table['header']]
    rows = []
    for cells in table['rows']:
        label = cells[0].strip()
        if label in skip_rows:
            continue
        rows.append({'item': label, 'values': [clean_number(v) for v in cells[1:]]})
    return {'columns': header[1:], 'rows': rows}


def section_for_statement(dataset, label, section):
    if dataset == 'balance':
        transitions = {
            'Total Noncurrent Assets': 'assets_noncurrent',
            'Total Assets': 'liabilities_current',
            'Total Current Liabilities': 'liabilities_noncurrent',
            'Total Noncurrent Liabilities': 'equity',
            'Total Liabilities': 'equity',
        }
        return transitions.get(label, section)
    if dataset == 'cashflow':
        transitions = {
            'Cash from Operating Activities': 'investing',
            'Cash from Investing Activities': 'financing',
            'Cash from Financing Activities': 'summary',
        }
        return transitions.get(label, section)
    return section


def statement_payload(content, dataset):
    table = parse_tables(content)[0]
    columns = table['header'][1:]
    as_of = []
    rows = []
    section = 'income' if dataset == 'income' else ('assets_current' if dataset == 'balance' else 'operating')
    for cells in table['rows']:
        label = cells[0].strip()
        values = [clean_number(v) for v in cells[1:]]
        if label == 'As of date':
            as_of = cells[1:]
            continue
        if label.startswith('##'):
            continue
        rows.append({'item': label, 'values': values, 'section': section})
        section = section_for_statement(dataset, label, section)
    return {'columns': columns, 'as_of': as_of, 'rows': rows}


def parse_snapshot(content):
    out = {}
    for line in content.splitlines():
        m = re.match(r'^-\s+([^:]+):\s*(.*)$', line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def parse_news(content):
    items = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith('- '):
            continue
        parts = [p.strip() for p in line[2:].split('|')]
        if len(parts) != 4:
            continue
        items.append({'published': parts[0], 'source': parts[1], 'title': parts[2], 'url': parts[3]})
    return items


def parse_quarterly(content):
    table = parse_tables(content)[0]
    header = table['header']
    quarters = header[1:]
    out = []
    for cells in table['rows']:
        year = cells[0].strip()
        for q, value in zip(quarters, cells[1:]):
            if q == 'FY':
                period, ptype = f'{year}-FY', 'annual'
            else:
                period, ptype = f'{year}-{q}', 'quarter'
            out.append({'period': period, 'period_type': ptype, 'year': int(year), 'quarter': q, 'value': clean_number(value)})
    return out


def build_payload():
    overviews = parse_sections(SOURCE / 'overview.md')
    financials = parse_sections(SOURCE / 'financials.md')
    snapshot = parse_snapshot(overviews['Snapshot'])
    overview_table = table_payload(parse_tables(overviews['Overview Metrics'])[0])
    cap_structure = table_payload(parse_tables(overviews['Capital Structure'])[0])
    working_capital = table_payload(parse_tables(overviews['Working Capital'])[0])
    growth = table_payload(parse_tables(overviews['Growth Rates'])[0])

    quarterly = {
        'revenue': {'unit': 'USD millions', 'rows': parse_quarterly(overviews['Quarterly Revenue'])},
        'eps': {'unit': 'USD/share', 'rows': parse_quarterly(overviews['Quarterly Earnings Per Share'])},
        'dps': {'unit': 'USD/share', 'rows': parse_quarterly(overviews['Quarterly Dividends Per Share'])},
    }

    statements = {
        'income': statement_payload(financials['Income Statement'], 'income'),
        'balance': statement_payload(financials['Balance Sheet'], 'balance'),
        'cashflow': statement_payload(financials['Cash Flow Statement'], 'cashflow'),
    }

    market_cap = snapshot.get('Market Cap', '').replace('B', '')
    market_cap_millions = round(float(market_cap) * 1000, 1) if market_cap.replace('.', '', 1).isdigit() else None

    company = {
        'ticker': TICKER,
        'name': snapshot.get('Name', 'QXO, Inc.'),
        'exchange': snapshot.get('Exchange', ''),
        'price': to_number(snapshot.get('Price')),
        'price_change': to_number(snapshot.get('Price Change')),
        'market_cap_millions': market_cap_millions,
        'sector': snapshot.get('Sector', ''),
        'industry': snapshot.get('Industry', ''),
        'ceo': snapshot.get('CEO', ''),
        'employees': to_number(snapshot.get('Employees')),
        'address': snapshot.get('Address', ''),
        'ipo_date': snapshot.get('IPO Date', ''),
        'cik': snapshot.get('CIK', ''),
        'isin': snapshot.get('ISIN', ''),
        'cusip': snapshot.get('CUSIP', ''),
        'website': snapshot.get('Website', ''),
        'description': snapshot.get('Description', ''),
        'business': overviews.get('Business', '').strip(),
        'source_overview': 'https://www.roic.ai/quote/QXO',
        'source_financials': 'https://www.roic.ai/quote/QXO/financials',
        'captured_at': CAPTURED,
    }

    return {
        'meta': {
            'ticker': TICKER,
            'captured_at': CAPTURED,
            'source_overview': company['source_overview'],
            'source_financials': company['source_financials'],
            'datasets': DATASET_LABELS,
        },
        'company': company,
        'snapshot': snapshot,
        'overview': overview_table,
        'capital_structure': cap_structure,
        'working_capital': working_capital,
        'growth': growth,
        'quarterly': quarterly,
        'statements': statements,
        'news': sorted(parse_news(overviews['News']), key=lambda item: item['published'], reverse=True),
    }


def build_facts(payload):
    facts = []

    def add(dataset, period, period_type, as_of, section, item, value, unit=None):
        facts.append({
            'ticker': TICKER, 'dataset': dataset, 'period': str(period), 'period_type': period_type,
            'as_of': as_of, 'section': section, 'item': item, 'value': value,
            'unit': unit or unit_for(item, dataset),
        })

    for col_idx, col in enumerate(payload['overview']['columns']):
        period, ptype, as_of = year_period(col)
        if not period:
            continue
        for row in payload['overview']['rows']:
            add('overview', period, ptype, as_of, '', row['item'], row['values'][col_idx])

    for dataset_key, dataset in (('capital_structure', payload['capital_structure']),
                                  ('working_capital', payload['working_capital'])):
        for col_idx, col in enumerate(dataset['columns']):
            period, ptype, as_of = snapshot_period(col)
            for row in dataset['rows']:
                add(dataset_key, period, ptype, as_of, '', row['item'], row['values'][col_idx])

    for col_idx, col in enumerate(payload['growth']['columns']):
        period = {'10 years': '10Y', '5 years': '5Y', '1 year': '1Y'}.get(col, col)
        for row in payload['growth']['rows']:
            add('growth', period, 'growth', None, '', row['item'], row['values'][col_idx], '%')

    for key, blob in payload['quarterly'].items():
        item = {'revenue': 'Revenue', 'eps': 'EPS', 'dps': 'Dividend per Share'}[key]
        for row in blob['rows']:
            add('quarterly', row['period'], row['period_type'],
                f"{row['year']}-12-31" if row['quarter'] == 'FY' else None,
                '', item, row['value'], blob['unit'])

    for dataset_key in ('income', 'balance', 'cashflow'):
        stmt = payload['statements'][dataset_key]
        for col_idx, col in enumerate(stmt['columns']):
            period, ptype, as_of = year_period(col)
            if not period:
                continue
            if col_idx < len(stmt['as_of']):
                as_of = stmt['as_of'][col_idx]
            for row in stmt['rows']:
                add(dataset_key, period, ptype, as_of, row['section'], row['item'], row['values'][col_idx])

    return facts


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT,
    price REAL,
    price_change REAL,
    market_cap_millions REAL,
    sector TEXT,
    industry TEXT,
    ceo TEXT,
    employees INTEGER,
    address TEXT,
    ipo_date TEXT,
    cik TEXT,
    isin TEXT,
    cusip TEXT,
    website TEXT,
    description TEXT,
    business TEXT,
    source_overview TEXT,
    source_financials TEXT,
    captured_at TEXT
);

CREATE TABLE facts (
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    dataset TEXT NOT NULL,
    period TEXT NOT NULL,
    period_type TEXT NOT NULL,
    as_of TEXT,
    section TEXT NOT NULL DEFAULT '',
    item TEXT NOT NULL,
    value REAL,
    unit TEXT,
    PRIMARY KEY (ticker, dataset, period, section, item)
);

CREATE TABLE news (
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    published TEXT,
    source TEXT,
    title TEXT,
    url TEXT,
    PRIMARY KEY (ticker, url)
);

CREATE INDEX idx_facts_dataset_item ON facts (dataset, item, period);
CREATE INDEX idx_facts_item ON facts (item);
CREATE INDEX idx_news_published ON news (published);

CREATE VIEW v_income AS SELECT * FROM facts WHERE dataset = 'income';
CREATE VIEW v_balance AS SELECT * FROM facts WHERE dataset = 'balance';
CREATE VIEW v_cashflow AS SELECT * FROM facts WHERE dataset = 'cashflow';
CREATE VIEW v_overview AS SELECT * FROM facts WHERE dataset = 'overview';
"""


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_sqlite(payload, facts, path):
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    company = payload['company']
    conn.execute(
        """INSERT INTO companies (ticker, name, exchange, price, price_change, market_cap_millions,
        sector, industry, ceo, employees, address, ipo_date, cik, isin, cusip, website, description,
        business, source_overview, source_financials, captured_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (company['ticker'], company['name'], company['exchange'], company['price'], company['price_change'],
         company['market_cap_millions'], company['sector'], company['industry'], company['ceo'],
         int(company['employees']) if company['employees'] is not None else None, company['address'],
         company['ipo_date'], company['cik'], company['isin'], company['cusip'], company['website'],
         company['description'], company['business'], company['source_overview'],
         company['source_financials'], company['captured_at'])
    )
    conn.executemany(
        """INSERT OR REPLACE INTO facts (ticker, dataset, period, period_type, as_of, section, item, value, unit)
        VALUES (:ticker, :dataset, :period, :period_type, :as_of, :section, :item, :value, :unit)""",
        facts,
    )
    conn.executemany(
        """INSERT OR REPLACE INTO news (ticker, published, source, title, url) VALUES (?,?,?,?,?)""",
        [(TICKER, n['published'], n['source'], n['title'], n['url']) for n in payload['news']],
    )
    conn.commit()
    conn.close()


def build_html(payload, facts, sql_dump):
    data_json = json.dumps(payload, separators=(',', ':')).replace('<', '\\u003c')
    sql_js = json.dumps(sql_dump)
    stats = {
        'facts': len(facts),
        'news': len(payload['news']),
        'datasets': len({f['dataset'] for f in facts}),
        'periods': len({(f['dataset'], f['period']) for f in facts}),
        'companies': 1,
    }
    page = (ROOT / 'template.html').read_text()
    page = page.replace('/*__STYLES__*/', (ROOT / 'styles.css').read_text())
    page = page.replace('/*__DATA__*/', 'const DATA = ' + data_json + ';')
    page = page.replace('/*__STATS__*/', 'const DB_STATS = ' + json.dumps(stats) + ';')
    page = page.replace('/*__SQL__*/', 'const SQL_DUMP = ' + sql_js + ';')
    page = page.replace('/*__APP__*/', (ROOT / 'app.js').read_text())
    assert not re.search(r'<script[^>]+src=', page), 'Standalone page must embed all scripts.'
    (ROOT / 'index.html').write_text(page)


def validate(payload):
    overview = payload['overview']
    years = overview['columns']
    ov = {row['item']: dict(zip(years, row['values'])) for row in overview['rows']}

    checks = {
        'income': ['Sales/Revenue/Turnover', 'Basic EPS, GAAP', 'Net Income, GAAP',
                   'Depreciation Expense', 'Operating Margin (%)', 'Profit Margin (%)',
                   'Dividend per Share'],
        'balance': ['Total Equity'],
    }
    for dataset, items in checks.items():
        stmt = payload['statements'][dataset]
        cols = stmt['columns']
        rows = {row['item']: dict(zip(cols, row['values'])) for row in stmt['rows']}
        for item in items:
            for year in cols:
                if year not in years:
                    continue
                expected, actual = ov[item][year], rows[item][year]
                if expected is not None and actual is not None:
                    assert abs(expected - actual) < 0.011, f'{item} {year}: overview {expected} != {dataset} {actual}'

    balance = payload['statements']['balance']
    rows = {row['item']: row['values'] for row in balance['rows']}
    for idx, year in enumerate(balance['columns']):
        assets, liab_eq = rows['Total Assets'][idx], rows['Total Liabilities & Equity'][idx]
        if assets is not None and liab_eq is not None:
            assert abs(assets - liab_eq) <= 1, f'Balance sheet does not balance in {year}: {assets} vs {liab_eq}'
    return True


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    validate(payload)
    facts = build_facts(payload)

    (DATA / 'qxo.json').write_text(json.dumps(payload, indent=2) + '\n')
    build_sqlite(payload, facts, ROOT / 'qxo.sqlite')
    conn = sqlite3.connect(ROOT / 'qxo.sqlite')
    sql_dump = '\n'.join(conn.iterdump()) + '\n'
    conn.close()
    (ROOT / 'qxo.sql').write_text(sql_dump)
    build_html(payload, facts, sql_dump)

    db = sqlite3.connect(ROOT / 'qxo.sqlite')
    counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
              for table in ('companies', 'facts', 'news')}
    db.close()
    print(f"Built index.html, data/qxo.json, qxo.sqlite, qxo.sql")
    print(f"Rows: {counts}")
    print(f"Facts: {len(facts)} across {len({f['dataset'] for f in facts})} datasets")


if __name__ == '__main__':
    main()
