import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class DCFCalculator:
    """
    Discounted Cash Flow (DCF) Model for Stock Valuation
    
    This class implements a comprehensive DCF model that calculates the fair value
    of a stock based on projected cash flows, growth rates, and discount rates.
    """
    
    def __init__(self):
        self.risk_free_rate = 0.04  # 4% risk-free rate (can be updated)
        self.market_risk_premium = 0.06  # 6% market risk premium
        self.terminal_growth_rate = 0.025  # 2.5% terminal growth rate
        
    def calculate_wacc(self, beta: float, debt_to_equity: float, 
                      tax_rate: float, cost_of_debt: float = None) -> float:
        """
        Calculate Weighted Average Cost of Capital (WACC)
        
        Args:
            beta: Stock's beta coefficient
            debt_to_equity: Debt to equity ratio
            tax_rate: Corporate tax rate
            cost_of_debt: Cost of debt (if None, estimated as risk_free_rate + 2%)
            
        Returns:
            WACC as decimal (e.g., 0.10 for 10%)
        """
        if cost_of_debt is None:
            cost_of_debt = self.risk_free_rate + 0.02
            
        # Cost of equity using CAPM
        cost_of_equity = self.risk_free_rate + beta * self.market_risk_premium
        
        # Calculate weights
        total_value = 1 + debt_to_equity
        weight_equity = 1 / total_value
        weight_debt = debt_to_equity / total_value
        
        # WACC formula
        wacc = (weight_equity * cost_of_equity + 
                weight_debt * cost_of_debt * (1 - tax_rate))
        
        return wacc
    
    def project_cash_flows(self, current_fcf: float, growth_rates: List[float], 
                          years: int = 5) -> pd.DataFrame:
        """
        Project future free cash flows
        
        Args:
            current_fcf: Current year free cash flow
            growth_rates: List of growth rates for each year
            years: Number of projection years
            
        Returns:
            DataFrame with projected cash flows
        """
        if len(growth_rates) != years:
            # If fewer growth rates provided, use the last rate for remaining years
            growth_rates = growth_rates + [growth_rates[-1]] * (years - len(growth_rates))
        
        projections = []
        fcf = current_fcf
        
        for year in range(1, years + 1):
            growth_rate = growth_rates[year - 1]
            fcf = fcf * (1 + growth_rate)
            projections.append({
                'Year': year,
                'Growth_Rate': growth_rate,
                'Free_Cash_Flow': fcf
            })
        
        return pd.DataFrame(projections)
    
    def calculate_terminal_value(self, final_fcf: float, wacc: float, 
                               terminal_growth: float = None) -> float:
        """
        Calculate terminal value using Gordon Growth Model
        
        Args:
            final_fcf: Free cash flow in the final projection year
            wacc: Weighted average cost of capital
            terminal_growth: Terminal growth rate (defaults to class default)
            
        Returns:
            Terminal value
        """
        if terminal_growth is None:
            terminal_growth = self.terminal_growth_rate
            
        if wacc <= terminal_growth:
            raise ValueError("WACC must be greater than terminal growth rate")
            
        terminal_value = (final_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        return terminal_value
    
    def calculate_enterprise_value(self, projected_fcf: pd.DataFrame, 
                                 terminal_value: float, wacc: float) -> Dict:
        """
        Calculate enterprise value and equity value
        
        Args:
            projected_fcf: DataFrame with projected cash flows
            terminal_value: Terminal value
            wacc: Weighted average cost of capital
            
        Returns:
            Dictionary with valuation metrics
        """
        # Discount projected cash flows
        projected_fcf['Discount_Factor'] = 1 / (1 + wacc) ** projected_fcf['Year']
        projected_fcf['Present_Value'] = (projected_fcf['Free_Cash_Flow'] * 
                                        projected_fcf['Discount_Factor'])
        
        # Sum of present values of projected cash flows
        pv_projected_fcf = projected_fcf['Present_Value'].sum()
        
        # Present value of terminal value
        final_year = projected_fcf['Year'].max()
        pv_terminal_value = terminal_value / (1 + wacc) ** final_year
        
        # Enterprise value
        enterprise_value = pv_projected_fcf + pv_terminal_value
        
        return {
            'pv_projected_fcf': pv_projected_fcf,
            'pv_terminal_value': pv_terminal_value,
            'enterprise_value': enterprise_value,
            'projected_fcf': projected_fcf
        }
    
    def calculate_fair_value(self, current_fcf: float, growth_rates: List[float],
                           beta: float, debt_to_equity: float, tax_rate: float,
                           shares_outstanding: float, net_debt: float = 0,
                           years: int = 5) -> Dict:
        """
        Complete DCF valuation calculation
        
        Args:
            current_fcf: Current year free cash flow
            growth_rates: List of growth rates for projection years
            beta: Stock's beta coefficient
            debt_to_equity: Debt to equity ratio
            tax_rate: Corporate tax rate
            shares_outstanding: Number of shares outstanding
            net_debt: Net debt (debt - cash)
            years: Number of projection years
            
        Returns:
            Dictionary with complete valuation results
        """
        # Calculate WACC
        wacc = self.calculate_wacc(beta, debt_to_equity, tax_rate)
        
        # Project cash flows
        projected_fcf = self.project_cash_flows(current_fcf, growth_rates, years)
        
        # Calculate terminal value
        final_fcf = projected_fcf.iloc[-1]['Free_Cash_Flow']
        terminal_value = self.calculate_terminal_value(final_fcf, wacc)
        
        # Calculate enterprise value
        ev_results = self.calculate_enterprise_value(projected_fcf, terminal_value, wacc)
        
        # Calculate equity value
        equity_value = ev_results['enterprise_value'] - net_debt
        
        # Calculate fair value per share
        fair_value_per_share = equity_value / shares_outstanding
        
        # Calculate key metrics
        final_year_fcf = projected_fcf.iloc[-1]['Free_Cash_Flow']
        fcf_yield = final_year_fcf / ev_results['enterprise_value']
        
        return {
            'wacc': wacc,
            'terminal_value': terminal_value,
            'enterprise_value': ev_results['enterprise_value'],
            'equity_value': equity_value,
            'fair_value_per_share': fair_value_per_share,
            'projected_fcf': projected_fcf,
            'pv_projected_fcf': ev_results['pv_projected_fcf'],
            'pv_terminal_value': ev_results['pv_terminal_value'],
            'final_year_fcf': final_year_fcf,
            'fcf_yield': fcf_yield,
            'net_debt': net_debt,
            'shares_outstanding': shares_outstanding
        }
    
    def sensitivity_analysis(self, base_params: Dict, 
                           wacc_range: Tuple[float, float] = (0.08, 0.15),
                           growth_range: Tuple[float, float] = (0.02, 0.08),
                           steps: int = 5) -> pd.DataFrame:
        """
        Perform sensitivity analysis on key parameters
        
        Args:
            base_params: Base case parameters
            wacc_range: Range of WACC values to test
            growth_range: Range of growth rates to test
            steps: Number of steps in each dimension
            
        Returns:
            DataFrame with sensitivity analysis results
        """
        wacc_values = np.linspace(wacc_range[0], wacc_range[1], steps)
        growth_values = np.linspace(growth_range[0], growth_range[1], steps)
        
        results = []
        
        for wacc in wacc_values:
            for growth in growth_values:
                # Create modified growth rates
                modified_growth_rates = [growth] * len(base_params['growth_rates'])
                
                # Calculate valuation with modified parameters
                valuation = self.calculate_fair_value(
                    current_fcf=base_params['current_fcf'],
                    growth_rates=modified_growth_rates,
                    beta=base_params['beta'],
                    debt_to_equity=base_params['debt_to_equity'],
                    tax_rate=base_params['tax_rate'],
                    shares_outstanding=base_params['shares_outstanding'],
                    net_debt=base_params.get('net_debt', 0),
                    years=len(modified_growth_rates)
                )
                
                results.append({
                    'WACC': wacc,
                    'Growth_Rate': growth,
                    'Fair_Value': valuation['fair_value_per_share'],
                    'Enterprise_Value': valuation['enterprise_value']
                })
        
        return pd.DataFrame(results)
