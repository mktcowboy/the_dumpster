import os
from datetime import date, datetime
import pandas as pd
import requests
import io
# Set working directory to the script's location
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def create_constituents(df):
    # create Dataframe with current constituents
    ticker_list = []
    for i, row in df.iterrows():
        tmp_val = row['ticker']
        ticker_list.append(tmp_val)

    res_string = ','.join(ticker_list)

    results_df = pd.DataFrame({'date': date.today(),
                               'tickers': [res_string],
                               })

    return results_df

def diff_tickers(nasdaq100):
    added_tickers = {}
    removed_tickers = {}

    for i in range(1, len(nasdaq100.index)):
        prev_tickers = set(nasdaq100.iloc[i - 1].tickers)
        current_tickers = set(nasdaq100.iloc[i].tickers)

        added = current_tickers - prev_tickers
        if added:
            nasdaq100_index_val = nasdaq100.index[i]
            added_tickers[nasdaq100_index_val] = list(added)

        removed = prev_tickers - current_tickers
        if removed:
            nasdaq100_index_val = nasdaq100.index[i]
            removed_tickers[nasdaq100_index_val] = list(removed)

    at_only = pd.DataFrame(added_tickers.items(), columns=['date', 'added_tickers'])
    rt_only = pd.DataFrame(removed_tickers.items(), columns=['date', 'removed_tickers'])
    combined = pd.merge(at_only, rt_only, on=['date'], how='outer')
    combined = combined.sort_values('date', ascending=True)
    combined = combined.set_index('date')
    
    return combined


def main():
    header = {
      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
      "X-Requested-With": "XMLHttpRequest"
    }

    # read historical data
    hist_filename = 'nasdaq_100_historical_components.csv'
    
    # Check if tracking file exists; if not, initialize an empty DataFrame with expected columns
    if os.path.exists(hist_filename):
        nasdaq100_hist = pd.read_csv(hist_filename)
    else:
        nasdaq100_hist = pd.DataFrame(columns=['date', 'tickers'])

    # current companies
    nasdaq_100_url = 'https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies'
    r = requests.get(nasdaq_100_url, headers=header)
    html_stream = io.StringIO(r.text)
    
    # Parse Wikipedia table and normalize headers
    nasdaq_100_constituents = pd.read_html(html_stream, header=0)[0].rename(columns=str.lower)

    # 3. Strip out Wikipedia footnote brackets (like) from column names using regex
    nasdaq_100_constituents.columns = nasdaq_100_constituents.columns.str.replace(r'\[.*\]', '', regex=True).str.strip()

    # add date
    nasdaq_100_constituents['date'] = date.today()

    # Save a copy of current components snapshot
    nasdaq_100_constituents.to_csv('nasdaq100_constituents.csv', index=False)
    
    # Clean up non-ticker columns. Using errors='ignore' ensures safety if columns change.
    columns_to_drop = ['company', 'icb industry', 'icb subsector']
    nasdaq_100_constituents.drop(columns_to_drop, axis=1, inplace=True, errors='ignore')

    # Ensure standard schema: ticker and date
    nasdaq_100_constituents.columns = ['ticker', 'date']
    nasdaq_100_constituents.sort_values(by='ticker', ascending=True, inplace=True)

    df = create_constituents(nasdaq_100_constituents)
    df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d")
    final = pd.concat([nasdaq100_hist, df], ignore_index=True)

    # output nasdaq_100_historical_components
    final = final.drop_duplicates(subset=['date', 'tickers'], keep='last')
    final.to_csv(hist_filename, index=False)

    # get added and removed components
    nasdaq100_historical = pd.read_csv(hist_filename, index_col='date')

    # Convert ticker string column to sorted lists for clean set logic comparison
    nasdaq100_historical['tickers'] = nasdaq100_historical['tickers'].apply(lambda x: sorted(x.split(',')))

    # sort dataframe by date
    nasdaq100_historical = nasdaq100_historical.sort_index()
    combined = diff_tickers(nasdaq100_historical)
    combined.to_csv('nasdaq100_changes.csv')

    # rewrite README.md with changes if data exists
    if not combined.empty:
        changes_readme = combined.iloc[-50:]
        changes_readme = changes_readme.sort_index(ascending=False)
        markdown_table = changes_readme.to_markdown()
    else:
        markdown_table = "No historical variations recorded yet."
    
    YML = "README.md"
    # Ensure file exists to replicate the original script's "r+" open mode dependency safely
    if not os.path.exists(YML):
        with open(YML, "w", encoding="UTF-8") as f:
            f.write("\n" * 10)
            
    f = open(YML, "r+", encoding="UTF-8")
    list1 = f.readlines()
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    list1 = list1[:10]
    list1 += [f'NASDAQ-100 Constituents Auto Renew at **{current_datetime}**']
    list1 += ['\n\n']
    list1 += [markdown_table]
    
    f = open(YML, "w+", encoding="UTF-8")
    f.writelines(list1)
    f.close()


if __name__ == '__main__':
    main()
