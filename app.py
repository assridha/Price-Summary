import streamlit as st
import requests
import pandas as pd
from datetime import timedelta, datetime
import streamlit.components.v1 as components

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
def get_block_height_7d_ago():
    """Fetches the block height from 7 days ago using mempool.space API."""
    try:
        # Get timestamp 7 days ago (in seconds)
        seven_days_ago = int((datetime.now() - timedelta(days=7)).timestamp())
        
        url = f"https://mempool.space/api/v1/mining/blocks/timestamp/{seven_days_ago}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        return data.get('height', 'N/A')
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching block height from 7 days ago: {e}")
    return 'N/A'

def calculate_issuance_per_block(current_block_height):
    """Calculate the current issuance per block using the halving formula."""
    if current_block_height == 'N/A':
        return 0
    
    # Formula: 3.125 * 2^(-floor([current block height]/210000-4))
    import math
    halving_cycles = math.floor(current_block_height / 210000 - 4)
    issuance = 3.125 * (2 ** (-halving_cycles))
    return issuance

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
        
        latest_total, week_ago_total = "N/A", "N/A"
        if len(df) > 0:
            latest_total = df.loc[0, columns_to_sum].sum()
            latest_timestamp = df.loc[0, 'timestamp']
            
            # Find entry closest to 7 days ago
            target_date = latest_timestamp - timedelta(days=7)
            
            # Find the index of the entry closest to 7 days ago
            df['time_diff'] = abs(df['timestamp'] - target_date)
            closest_idx = df['time_diff'].idxmin()
            
            if closest_idx is not None:
                week_ago_total = df.loc[closest_idx, columns_to_sum].sum()
            
        return latest_total, week_ago_total
    except Exception as e:
        st.error(f"Error fetching institutional holdings: {e}")
    return "N/A", "N/A"

st.set_page_config(page_title="Bitcoin Metrics Dashboard", layout="wide")

# st.title("Bitcoin at a Glance")

# Fetch data
btc_data = get_coingecko_data()
block_height = get_block_height()
block_height_7d_ago = get_block_height_7d_ago()
avg_block_time = get_avg_block_time()
difficulty_data = get_difficulty_adjustment()
latest_ma, prev_ma = get_onchain_volume_mas()
institutional_btc, week_ago_institutional_btc = get_institutional_btcs()

if btc_data:
    st.subheader("Price and Market Cap", anchor=False)
    # Display Price and Market Cap
    col1, col2 = st.columns(2)
    price = btc_data.get('current_price', 'N/A')
    price_change = btc_data.get('price_change_percentage_24h', 0)
    
    col1.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Price</p>', unsafe_allow_html=True)
    price_value_str = f'<p style="font-size: 28px; line-height: 1;">${price:,.0f}</p>'
    col1.markdown(price_value_str, unsafe_allow_html=True)
    if price_change is not None:
        color = "#2E8B57" if price_change >= 0 else "#D22B2B"
        arrow = "▲" if price_change >= 0 else "▼"
        delta_str = f"{abs(price_change):.2f}% (24h)"
        col1.markdown(f'<p style="font-size: 0.875rem; color: {color}; margin:0;">{arrow} {delta_str}</p>', unsafe_allow_html=True)

    market_cap = btc_data.get('market_cap', 'N/A')

    if market_cap != 'N/A':
        if market_cap > 1_000_000_000_000:
            mc_display = f"${market_cap/1_000_000_000_000:.2f} T"
        elif market_cap > 1_000_000_000:
            mc_display = f"${market_cap/1_000_000_000:.2f} B"
        else:
            mc_display = f"${market_cap/1_000_000:.2f} M"
        
        col2.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Market Cap</p>', unsafe_allow_html=True)
        mc_value_str = f'<p style="font-size: 28px; line-height: 1;">{mc_display}</p>'
        col2.markdown(mc_value_str, unsafe_allow_html=True)
    else:
        col2.metric("Market Cap", "N/A")
    
    st.markdown("---")
    
    # Display Blockchain stats
    st.subheader("Blockchain Stats", anchor=False)
    col1, col2, col3 = st.columns(3)

    if block_height != "N/A":
        col1.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Block Height</p>', unsafe_allow_html=True)
        bh_value_str = f'<p style="font-size: 28px; line-height: 1;">{int(block_height):,}</p>'
        col1.markdown(bh_value_str, unsafe_allow_html=True)
    else:
        col1.metric("Block Height", "N/A")

    if avg_block_time != "N/A":
        col2.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Avg Block Time</p>', unsafe_allow_html=True)
        abt_value_str = f'<p style="font-size: 28px; line-height: 1;">{avg_block_time:.2f}s</p>'
        col2.markdown(abt_value_str, unsafe_allow_html=True)
        delta_time = avg_block_time - 600
        # For block time, lower is better. So red for positive delta.
        color = "#2E8B57" if delta_time <= 0 else "#D22B2B"
        arrow = "▼" if delta_time <= 0 else "▲"
        delta_str = f"{abs(delta_time):.2f}s vs target"
        col2.markdown(f'<p style="font-size: 0.875rem; color: {color}; margin:0;">{arrow} {delta_str}</p>', unsafe_allow_html=True)
    else:
        col2.metric("Avg Block Time", "N/A")

    if difficulty_data and isinstance(difficulty_data, list) and len(difficulty_data) > 0:
        latest_adjustment = difficulty_data[0]
        if isinstance(latest_adjustment, list) and len(latest_adjustment) >= 4:
            difficulty = latest_adjustment[2]
            change_factor = latest_adjustment[3]
            
            difficulty_in_terra = difficulty / (10**12)
            difficulty_change_percent = (change_factor - 1) * 100
            
            col3.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Latest Difficulty</p>', unsafe_allow_html=True)
            diff_value_str = f'<p style="font-size: 28px; line-height: 1;">{difficulty_in_terra:.2f} T</p>'
            col3.markdown(diff_value_str, unsafe_allow_html=True)
            # For difficulty, higher is better for network security.
            color = "#2E8B57" if difficulty_change_percent >= 0 else "#D22B2B"
            arrow = "▲" if difficulty_change_percent >= 0 else "▼"
            delta_str = f"{abs(difficulty_change_percent):.2f}%"
            col3.markdown(f'<p style="font-size: 0.875rem; color: {color}; margin:0;">{arrow} {delta_str}</p>', unsafe_allow_html=True)
        else:
            col3.metric("Latest Difficulty", "N/A")
    else:
        col3.metric("Latest Difficulty", "N/A")

    st.markdown("---")

    # Display Supply and Volume metrics
    st.subheader("Supply & Volume", anchor=False)
    col1, col2, col3 = st.columns(3)

    circulating_supply = btc_data.get('circulating_supply', 'N/A')
    total_supply = 21000000

    if circulating_supply != 'N/A':
        supply_increase_delta = None
        if block_height != "N/A" and block_height_7d_ago != "N/A":
            try:
                current_height = int(block_height)
                height_7d_ago = int(block_height_7d_ago)
                
                # Calculate blocks mined in the last 7 days
                blocks_mined = current_height - height_7d_ago
                
                # Calculate issuance per block
                issuance_per_block = calculate_issuance_per_block(current_height)
                
                # Calculate total supply increase over 7 days
                supply_increase = blocks_mined * issuance_per_block
                
                # Calculate daily average
                daily_avg_supply_increase = supply_increase / 7
                
                supply_increase_delta = f"{daily_avg_supply_increase:.0f} BTC/day"
            except (ValueError, TypeError):
                supply_increase_delta = None
        
        col1.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Circulating Supply</p>', unsafe_allow_html=True)
        supply_str_value = f"""
        <div style="display: flex; align-items: baseline; justify-content: left; line-height: 1;">
            <span style="font-size: 28px;">{int(circulating_supply):,}</span>
            <span style="font-size: 16px; margin-left: 8px;">BTC</span>
        </div>
        """
        col1.markdown(supply_str_value, unsafe_allow_html=True)
        if supply_increase_delta:
            col1.markdown(f'<p style="font-size: 0.875rem; color: #2E8B57; margin:0;">▲ {supply_increase_delta}</p>', unsafe_allow_html=True)

        percentage_of_terminal = circulating_supply / total_supply
        p_col1, _ = col1.columns([0.8, 0.2])
        p_col1.progress(percentage_of_terminal)
        col1.markdown(f'<p style="margin-top: -1rem; font-size: 0.875rem;">{percentage_of_terminal:.2%} of 21M</p>', unsafe_allow_html=True)
    else:
        col1.metric("Circulating Supply", "N/A")

    if institutional_btc != "N/A":
        daily_avg_delta = 0
        if week_ago_institutional_btc != "N/A" and week_ago_institutional_btc > 0:
            delta = institutional_btc - week_ago_institutional_btc
            daily_avg_delta = delta / 7
        
        tooltip_text = """Institutional Holdings tracks Bitcoin held by: Public companies (MicroStrategy, Tesla, etc.), Private companies, Mining companies, Countries/governments, ETFs and DeFi protocols.
Data is updated daily and sourced from bitbo.io. Change shown is daily average over the past 7 days.
"""
        
        col2.markdown(f'<p style="font-size: 0.875rem; color: black; margin:0;" title="{tooltip_text.strip()}">Institutional Holdings</p>', unsafe_allow_html=True)
        institutional_btc_str_value = f"""
        <div style="display: flex; align-items: baseline; justify-content: left; line-height: 1;">
            <span style="font-size: 28px;">{int(institutional_btc):,}</span>
            <span style="font-size: 16px; margin-left: 8px;">BTC</span>
        </div>
        """
        col2.markdown(institutional_btc_str_value, unsafe_allow_html=True)

        if daily_avg_delta == 0:
            delta_str = "No Change"
            color = "grey"
            arrow = ""
        else:
            delta_str = f"{abs(daily_avg_delta):,.0f} BTC/day"
            color = "#2E8B57" if daily_avg_delta > 0 else "#D22B2B"
            arrow = "▲" if daily_avg_delta > 0 else "▼"
        col2.markdown(f'<p style="font-size: 0.875rem; color: {color}; margin:0;">{arrow} {delta_str}</p>', unsafe_allow_html=True)
        
        percentage_of_total_supply = institutional_btc / total_supply
        p_col2, _ = col2.columns([0.8, 0.2])
        p_col2.progress(percentage_of_total_supply)
        col2.markdown(f'<p style="margin-top: -1rem; font-size: 0.875rem;">{percentage_of_total_supply:.2%} of 21M</p>', unsafe_allow_html=True)
    else:
        tooltip_text = """Institutional Holdings** tracks Bitcoin held by: Public companies (MicroStrategy, Tesla, etc.), Private companies, Mining companies, Countries/governments, ETFs and investment funds and DeFi protocols.
Data is updated daily and sourced from bitbo.io. Change shown is daily average over the past 7 days.
"""
        col2.metric(label="Institutional Holdings", value="N/A", help=tooltip_text)

    if latest_ma != "N/A":
        col3.markdown('<p style="font-size: 0.875rem; color: black; margin:0;">Daily Onchain Volume (7d MA)</p>', unsafe_allow_html=True)
        latest_ma_str_value = f"""
        <div style="display: flex; align-items: baseline; justify-content: left; line-height: 1;">
            <span style="font-size: 28px;">{int(latest_ma):,}</span>
            <span style="font-size: 16px; margin-left: 8px;">BTC</span>
        </div>
        """
        col3.markdown(latest_ma_str_value, unsafe_allow_html=True)

        if prev_ma != "N/A" and prev_ma > 0:
            delta = latest_ma - prev_ma
            delta_percent = (delta / prev_ma) * 100
            color = "#2E8B57" if delta > 0 else "#D22B2B"
            arrow = "▲" if delta > 0 else "▼"
            delta_str = f"{abs(delta_percent):.2f}% today"
            col3.markdown(f'<p style="font-size: 0.875rem; color: {color}; margin:0;">{arrow} {delta_str}</p>', unsafe_allow_html=True)
        else:
            col3.markdown('<p style="font-size: 0.875rem; color: grey; margin:0;">No Change</p>', unsafe_allow_html=True)
    else:
        col3.metric("Daily Onchain Volume (7d MA)", "N/A")

else:
    st.error("Could not fetch Bitcoin data. Please try again later.")

st.markdown("""
<style>
/* Remove all padding from the main block container */
.block-container {
    padding: 0rem !important;
}

/* Flatten the metric containers to remove card look */
div[data-testid="metric-container"] {
    border: none !important;
    background-color: transparent !important;
    border-radius: 0 !important;
    padding: 1rem 0 !important; /* Give metrics some vertical space */
}

div[data-testid="stMetricValue"] {
    font-size: 28px;
}
hr {
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
}
h2 {
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
}

/* Tooltip styles */
.tooltip-container {
    position: relative;
    display: inline-block;
    cursor: help;
}

.tooltip-text {
    display: inline-block;
}

.tooltip-content {
    visibility: hidden;
    width: 300px;
    background-color: #333;
    color: #fff;
    text-align: left;
    border-radius: 6px;
    padding: 12px;
    position: absolute;
    z-index: 1000;
    bottom: 125%;
    left: 50%;
    margin-left: -150px;
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 14px;
    line-height: 1.4;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.tooltip-content::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: #333 transparent transparent transparent;
}

.tooltip-container:hover .tooltip-content {
    visibility: visible;
    opacity: 1;
}

@media (max-width: 800px) {
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 1rem !important;
    }

    /* Target each column div directly within the horizontal block */
    div[data-testid="stHorizontalBlock"] > div {
        flex: 1 1 calc(50% - 1rem) !important;
        min-width: calc(50% - 1rem) !important;
    }
    
    /* Mobile tooltip adjustments */
    .tooltip-content {
        width: 250px;
        margin-left: -125px;
        font-size: 12px;
    }
}
</style>
""", unsafe_allow_html=True)
