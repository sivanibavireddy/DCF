from flask import Flask, render_template, request, jsonify, session
import json
import pandas as pd
import numpy as np
from datetime import datetime
import os
import base64
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from dcf_calculator import DCFCalculator
from data_interface import StockDataInterface

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dcf-val-secret-key-2024')

# Initialize components
dcf_calc = DCFCalculator()
data_interface = StockDataInterface()

# Set up plotting style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

@app.route('/')
def landing():
    """Landing page with DCF explanation"""
    return render_template('landing.html')

@app.route('/analyze')
def index():
    """Analysis page with DCF analysis form"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """Analyze a stock using DCF model"""
    try:
        data = request.get_json()
        
        ticker = data.get('ticker', '').upper()
        growth_rates = [float(x) for x in data.get('growth_rates', [])]
        tax_rate = float(data.get('tax_rate', 0.25))
        years = int(data.get('years', 5))
        
        if not ticker:
            return jsonify({'error': 'Ticker symbol is required'}), 400
        
        if not ticker or len(ticker) < 1 or len(ticker) > 20:
            return jsonify({'error': f'Invalid ticker symbol: {ticker}. Please enter a valid stock ticker (1-20 characters).'}), 400
        
        # Get stock data
        stock_info = data_interface.get_stock_info(ticker)
        if not stock_info or not stock_info.get('name'):
            return jsonify({'error': f'Stock not found: {ticker}. Please check the ticker symbol and try again.'}), 400
        
        # Get financial statements
        financials = data_interface.get_financial_statements(ticker)
        
        # Calculate historical FCF
        fcf_history = data_interface.calculate_free_cash_flow(ticker, years)
        
        if fcf_history.empty:
            try:
                cash_flow = financials.get('cash_flow', pd.DataFrame())
                if not cash_flow.empty:
                    latest_fcf = None
                    for i, (date, row) in enumerate(cash_flow.iterrows()):
                        if i >= 1:
                            break
                        fcf = row.get('Free Cash Flow', 0)
                        if pd.notna(fcf) and fcf != 0:
                            latest_fcf = fcf
                            break
                    
                    if latest_fcf is not None:
                        current_fcf = latest_fcf
                    else:
                        current_fcf = estimate_fcf_from_net_income(stock_info)
                        if current_fcf is None:
                            return jsonify({'error': f'No FCF data available for {ticker}.'}), 400
                else:
                    current_fcf = estimate_fcf_from_net_income(stock_info)
                    if current_fcf is None:
                        return jsonify({'error': f'No FCF data available for {ticker}.'}), 400
            except Exception as e:
                current_fcf = estimate_fcf_from_net_income(stock_info)
                if current_fcf is None:
                    return jsonify({'error': f'No FCF data available for {ticker}.'}), 400
        else:
            current_fcf = fcf_history.iloc[-1]['Free_Cash_Flow']
        
        if current_fcf <= 0:
            return jsonify({'error': f'No valid FCF data available for {ticker}.'}), 400
        
        net_debt = stock_info.get('total_debt', 0) - stock_info.get('cash', 0)
        
        shares_outstanding = stock_info.get('shares_outstanding', 1)
        if shares_outstanding <= 0:
            shares_outstanding = 1
        
        try:
            valuation = dcf_calc.calculate_fair_value(
                current_fcf=current_fcf,
                growth_rates=growth_rates,
                beta=stock_info.get('beta', 1.0),
                debt_to_equity=stock_info.get('debt_to_equity', 0),
                tax_rate=tax_rate,
                shares_outstanding=shares_outstanding,
                net_debt=net_debt,
                years=len(growth_rates)
            )
            
            fair_value = valuation.get('fair_value_per_share', 0)
            if fair_value <= 0:
                return jsonify({'error': f'Invalid DCF calculation result for {ticker}.'}), 400
                
        except Exception as e:
            return jsonify({'error': f'DCF calculation failed for {ticker}: {str(e)}'}), 400
        
        valuation.update({
            'ticker': ticker,
            'stock_name': stock_info.get('name', ticker),
            'current_price': stock_info.get('current_price', 0),
            'market_cap': stock_info.get('market_cap', 0),
            'fcf_history': fcf_history.to_dict('records'),
            'stock_info': stock_info
        })
        
        current_price = stock_info.get('current_price', 0)
        if current_price > 0:
            upside = ((valuation['fair_value_per_share'] - current_price) / current_price) * 100
            valuation['upside_percentage'] = upside
            
            if upside > 20:
                recommendation = "STRONG BUY"
                recommendation_color = "success"
            elif upside > 10:
                recommendation = "BUY"
                recommendation_color = "success"
            elif upside > -10:
                recommendation = "HOLD"
                recommendation_color = "warning"
            elif upside > -20:
                recommendation = "SELL"
                recommendation_color = "danger"
            else:
                recommendation = "STRONG SELL"
                recommendation_color = "danger"
            
            valuation['recommendation'] = recommendation
            valuation['recommendation_color'] = recommendation_color
        
        if 'projected_fcf' in valuation:
            valuation['projected_fcf'] = valuation['projected_fcf'].to_dict('records')
        
        return jsonify(valuation)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sensitivity', methods=['POST'])
def sensitivity_analysis():
    """Perform sensitivity analysis"""
    try:
        data = request.get_json()
        
        base_params = {
            'current_fcf': float(data.get('current_fcf', 0)),
            'growth_rates': [float(x) for x in data.get('growth_rates', [])],
            'beta': float(data.get('beta', 1.0)),
            'debt_to_equity': float(data.get('debt_to_equity', 0)),
            'tax_rate': float(data.get('tax_rate', 0.25)),
            'shares_outstanding': float(data.get('shares_outstanding', 1)),
            'net_debt': float(data.get('net_debt', 0))
        }
        
        sensitivity_results = dcf_calc.sensitivity_analysis(base_params)
        
        return jsonify({
            'sensitivity_data': sensitivity_results.to_dict('records')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stock_info/<ticker>')
def get_stock_info(ticker):
    """Get basic stock information"""
    try:
        stock_info = data_interface.get_stock_info(ticker)
        recommendations = data_interface.get_analyst_recommendations(ticker)
        earnings = data_interface.get_earnings_calendar(ticker)
        
        return jsonify({
            'stock_info': stock_info,
            'recommendations': recommendations,
            'earnings': earnings
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/popular_stocks')
def get_popular_stocks():
    """Get list of popular stocks for quick selection"""
    market = request.args.get('market', 'US')
    
    if market == 'IN':
        popular_stocks = [
            {'ticker': 'RELIANCE.NS', 'name': 'Reliance Industries Ltd.', 'sector': 'Energy'},
            {'ticker': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'Technology'},
            {'ticker': 'HDFCBANK.NS', 'name': 'HDFC Bank Ltd.', 'sector': 'Banking'},
            {'ticker': 'INFY.NS', 'name': 'Infosys Ltd.', 'sector': 'Technology'},
            {'ticker': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever Ltd.', 'sector': 'Consumer Goods'},
            {'ticker': 'ICICIBANK.NS', 'name': 'ICICI Bank Ltd.', 'sector': 'Banking'},
            {'ticker': 'BHARTIARTL.NS', 'name': 'Bharti Airtel Ltd.', 'sector': 'Telecom'},
            {'ticker': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'Banking'},
            {'ticker': 'WIPRO.NS', 'name': 'Wipro Ltd.', 'sector': 'Technology'},
            {'ticker': 'ITC.NS', 'name': 'ITC Ltd.', 'sector': 'Consumer Goods'}
        ]
    else:
        popular_stocks = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
            {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology'},
            {'ticker': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology'},
            {'ticker': 'AMZN', 'name': 'Amazon.com Inc.', 'sector': 'Consumer Discretionary'},
            {'ticker': 'TSLA', 'name': 'Tesla Inc.', 'sector': 'Consumer Discretionary'},
            {'ticker': 'META', 'name': 'Meta Platforms Inc.', 'sector': 'Technology'},
            {'ticker': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology'},
            {'ticker': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'Financial Services'},
            {'ticker': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare'},
            {'ticker': 'V', 'name': 'Visa Inc.', 'sector': 'Financial Services'}
        ]
    
    return jsonify(popular_stocks)

def estimate_fcf_from_net_income(stock_info):
    try:
        net_income = stock_info.get('net_income', 0)
        if net_income and net_income > 0:
            return net_income * 0.75
        return None
    except:
        return None

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
