import streamlit as st
import requests
import pandas as pd
from datetime import timedelta, datetime

# Cache data for 60 seconds
@st.cache_data(ttl=timedelta(minutes=1))
def get_coingecko_data():
    """Fetches Bitcoin data from the CoinGecko API."""
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin&price_change_percentage=24h"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors
        data = response.json()
        if data:
            return data[0]
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from CoinGecko: {e}")
    return None

@st.cache_data(ttl=timedelta(minutes=1))
def get_block_height():
    """Fetches the current block height."""
    url = "https://blockchain.info/q/getblockcount"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching block height: {e}")
    return "N/A"

@st.cache_data(ttl=timedelta(minutes=10))
def get_avg_block_time():
    """Fetches the average block time."""
    url = "https://blockchain.info/q/interval"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return float(response.text)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching average block time: {e}")
    return "N/A"

@st.cache_data(ttl=timedelta(minutes=10))
def get_difficulty_adjustment():
    """Fetches last month's difficulty adjustment data."""
    url = "https://mempool.space/api/v1/mining/difficulty-adjustments/1m"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching difficulty adjustment data: {e}")
    return None

@st.cache_data(ttl=timedelta(hours=6))
def get_onchain_volume_mas():
    """Fetches and calculates the 7-day moving average of on-chain volume."""
    url = "https://api.blockchain.info/charts/estimated-transaction-volume?format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['values'])
        mas = df['y'].rolling(window=7).mean()
        if len(mas.dropna()) >= 2:
            return mas.dropna().iloc[-1], mas.dropna().iloc[-2]
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        st.error(f"Error processing on-chain volume: {e}")
    return "N/A", "N/A"

@st.cache_data(ttl=timedelta(hours=24))
def get_institutional_btcs():
    """Calculates total BTC held by institutions from the latest entry in a CSV file."""
    url = "https://raw.githubusercontent.com/assridha/BTC-Treasury/main/category_btc-treasuries.csv"
    try:
        df = pd.read_csv(url)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by='timestamp', ascending=False).reset_index(drop=True)
        columns_to_sum = [
            'btc_mining_companies', 'countries', 'defi', 'etfs',
            'private_companies', 'public_companies'
        ]
        
        latest_total, previous_total = "N/A", "N/A"
        if len(df) > 0:
            latest_total = df.loc[0, columns_to_sum].sum()
        if len(df) > 1:
            previous_total = df.loc[1, columns_to_sum].sum()
            
        return latest_total, previous_total
    except Exception as e:
        st.error(f"Error fetching institutional holdings: {e}")
    return "N/A", "N/A"

st.set_page_config(page_title="Bitcoin Metrics Dashboard", layout="wide")

st.title("Bitcoin Price & Metrics")

# Fetch data
btc_data = get_coingecko_data()
block_height = get_block_height()
avg_block_time = get_avg_block_time()
difficulty_data = get_difficulty_adjustment()
latest_ma, prev_ma = get_onchain_volume_mas()
institutional_btc, prev_institutional_btc = get_institutional_btcs()

if btc_data:
    # Display Price and 24h Return
    col1, col2 = st.columns([3, 1]) 
    price = btc_data.get('current_price', 'N/A')
    price_change = btc_data.get('price_change_percentage_24h', 0)
    
    col1.metric("Price", f"${price:,.0f}", f"{price_change:.2f}%")
    
    st.markdown("---")
    
    # Display Blockchain stats
    st.subheader("Blockchain Stats")
    col1, col2, col3 = st.columns(3)

    if block_height != "N/A":
        col1.metric("Block Height", f"{int(block_height):,}")
    else:
        col1.metric("Block Height", "N/A")

    if avg_block_time != "N/A":
        col2.metric("Avg Block Time", f"{avg_block_time:.2f}s", f"{avg_block_time - 600:.2f}s vs target")
    else:
        col2.metric("Avg Block Time", "N/A")

    if difficulty_data and isinstance(difficulty_data, list) and len(difficulty_data) > 0:
        latest_adjustment = difficulty_data[0]
        if isinstance(latest_adjustment, list) and len(latest_adjustment) >= 4:
            difficulty = latest_adjustment[2]
            change_factor = latest_adjustment[3]
            
            difficulty_in_terra = difficulty / (10**12)
            difficulty_change_percent = (change_factor - 1) * 100
            col3.metric("Latest Difficulty", f"{difficulty_in_terra:.2f} T", f"{difficulty_change_percent:+.2f}%")
        else:
            col3.metric("Latest Difficulty", "N/A")
    else:
        col3.metric("Latest Difficulty", "N/A")

    st.markdown("---")

    # Display Supply and Volume metrics
    st.subheader("Supply & Volume")
    col1, col2, col3 = st.columns(3)

    circulating_supply = btc_data.get('circulating_supply', 'N/A')
    total_supply = 21000000

    if circulating_supply != 'N/A':
        daily_increase_delta = None
        if avg_block_time != "N/A" and avg_block_time > 0:
            daily_increase = 270000 / avg_block_time
            daily_increase_delta = f"{int(daily_increase):,}"
        
        col1.metric("Circulating Supply", f"{int(circulating_supply):,}", delta=daily_increase_delta)

        percentage_of_terminal = circulating_supply / total_supply
        p_col1, _ = col1.columns([0.8, 0.2])
        p_col1.progress(percentage_of_terminal)
        col1.markdown(f'<p style="margin-top: -1rem; font-size: 0.875rem;">{percentage_of_terminal:.2%} of Terminal Supply</p>', unsafe_allow_html=True)
    else:
        col1.metric("Circulating Supply", "N/A")

    if institutional_btc != "N/A":
        delta_str = "No Change"
        if prev_institutional_btc != "N/A" and prev_institutional_btc > 0:
            delta = institutional_btc - prev_institutional_btc
            delta_str = f"{delta:,.0f}"
        col2.metric("Institutional Holdings", f"{int(institutional_btc):,}", delta=delta_str)
        percentage_of_total_supply = institutional_btc / total_supply
        p_col2, _ = col2.columns([0.8, 0.2])
        p_col2.progress(percentage_of_total_supply)
        col2.markdown(f'<p style="margin-top: -1rem; font-size: 0.875rem;">{percentage_of_total_supply:.2%} of Terminal Supply</p>', unsafe_allow_html=True)
    else:
        col2.metric("Institutional Holdings", "N/A")

    if latest_ma != "N/A":
        delta_str = "No Change"
        if prev_ma != "N/A" and prev_ma > 0:
            delta = latest_ma - prev_ma
            delta_percent = (delta / prev_ma) * 100
            delta_str = f"{delta:,.0f} ({delta_percent:+.2f}%)"
        col3.metric("7d On-chain Volume MA", f"{int(latest_ma):,}", delta=delta_str)
    else:
        col3.metric("7d On-chain Volume MA", "N/A")

else:
    st.error("Could not fetch Bitcoin data. Please try again later.")

st.markdown("""
<style>
div[data-testid="metric-container"] {
    border-radius: 10px;
    padding: 20px;
    background-color: #f0f2f6;
    border: 1px solid #e6e6e6;
}
div[data-testid="stMetricValue"] {
    font-size: 28px;
}
</style>
""", unsafe_allow_html=True) 