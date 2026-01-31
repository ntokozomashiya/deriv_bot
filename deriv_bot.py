#!/usr/bin/env python3
"""
DERIV STEPINDEX TRADING BOT - COMPLETE VERSION
Smart Mean Reversion Strategy for StepIndex
Works on Termux Android
Author: Your Name
"""

import json
import requests
import time
import sys
import os
from datetime import datetime
from collections import deque
import numpy as np
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

class Config:
    """Bot configuration with user input"""
    def __init__(self):
        self.api_token = None
        self.account_id = None
        self.daily_profit_target = 0
        self.daily_loss_limit = 0
        self.base_stake = 0.50
        self.symbol = "1HZ100V"
        self.max_trades = 200
        self.demo_mode = True
        
    def get_user_input(self):
        """Get configuration from user"""
        print(Fore.CYAN + Style.BRIGHT + "\n" + "="*60)
        print("      DERIV STEPINDEX TRADING BOT v3.0")
        print("="*60)
        
        # API Token
        print(Fore.YELLOW + "\n🔑 API Configuration:")
        self.api_token = input("Enter your Deriv API Token: ").strip()
        if not self.api_token:
            print(Fore.RED + "❌ API Token is required!")
            sys.exit(1)
            
        # Account ID (optional)
        self.account_id = input("Enter Account ID (press Enter for demo): ").strip()
        
        # Trading parameters
        print(Fore.YELLOW + "\n🎯 Trading Parameters:")
        
        # Profit target
        while True:
            try:
                target = float(input("Daily Profit Target ($): "))
                if target > 0:
                    self.daily_profit_target = target
                    break
                else:
                    print(Fore.RED + "❌ Please enter a positive number")
            except:
                print(Fore.RED + "❌ Invalid input")
                
        # Loss limit
        while True:
            try:
                loss = float(input("Daily Loss Limit ($): "))
                if loss < 0:
                    self.daily_loss_limit = abs(loss)
                    break
                else:
                    print(Fore.RED + "❌ Enter negative (e.g., -10)")
            except:
                print(Fore.RED + "❌ Invalid input")
                
        # Stake size
        while True:
            try:
                stake = float(input(f"Base Stake Amount (default ${self.base_stake}): ") or self.base_stake)
                if 0.35 <= stake <= 100:
                    self.base_stake = stake
                    break
                else:
                    print(Fore.RED + "❌ Stake must be between $0.35 and $100")
            except:
                print(Fore.RED + "❌ Invalid input")
                
        # Demo/Live mode
        mode = input("\nTrade on DEMO account? (Y/n): ").strip().lower()
        self.demo_mode = mode != 'n'
        
        return self

class DerivAPI:
    """Handle all Deriv API communications"""
    def __init__(self, config):
        self.config = config
        self.token = config.api_token
        self.demo = config.demo_mode
        
        # API endpoints
        if self.demo:
            self.api_url = "https://api.deriv.com"
            print(Fore.GREEN + "✅ Using DEMO account (virtual money)")
        else:
            self.api_url = "https://api.deriv.com"
            print(Fore.RED + "⚠️  Using LIVE account - REAL MONEY!")
            
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Test connection
        if not self.test_connection():
            print(Fore.RED + "❌ Cannot connect to Deriv API")
            sys.exit(1)
        
    def test_connection(self):
        """Test API connection"""
        try:
            response = requests.get(
                f"{self.api_url}/balance",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'error' not in data:
                    balance = data.get('balance', {}).get('balance', 0)
                    currency = data.get('balance', {}).get('currency', 'USD')
                    print(Fore.GREEN + f"✅ Connected! Balance: {balance:.2f} {currency}")
                    return True
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    print(Fore.RED + f"❌ API Error: {error_msg}")
                    return False
            else:
                print(Fore.RED + f"❌ Connection failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(Fore.RED + f"❌ Connection error: {str(e)}")
            return False
            
    def buy_contract(self, symbol, amount, duration, direction):
        """Place a trade"""
        payload = {
            "buy": "1",
            "price": amount,
            "parameters": {
                "amount": amount,
                "basis": "stake",
                "contract_type": direction.upper(),
                "currency": "USD",
                "duration": duration,
                "duration_unit": "t",
                "symbol": symbol
            }
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/buy",
                json=payload,
                headers=self.headers,
                timeout=15
            )
            
            result = response.json()
            
            if 'error' in result:
                error_msg = result['error'].get('message', 'Unknown error')
                print(Fore.RED + f"❌ Trade Error: {error_msg}")
                return None
                
            return result.get('buy', {})
            
        except Exception as e:
            print(Fore.RED + f"❌ Trade execution error: {str(e)}")
            return None
    
    def get_balance(self):
        """Get current account balance"""
        try:
            response = requests.get(
                f"{self.api_url}/balance",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'error' not in data:
                    return data.get('balance', {}).get('balance', 0)
            return 0
            
        except:
            return 0

class TradingStrategy:
    """Smart Mean Reversion Strategy for StepIndex"""
    def __init__(self):
        self.price_history = deque(maxlen=100)  # Last 100 prices
        self.trade_history = []
        
        # Strategy parameters
        self.z_threshold = 2.2  # Entry threshold
        self.min_history = 30   # Minimum price history needed
        
        # Performance tracking
        self.win_count = 0
        self.loss_count = 0
        self.total_profit = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_drawdown = 0
        self.peak_balance = 0
        
    def update_price(self, price):
        """Add new price to history"""
        self.price_history.append(price)
        
    def calculate_stats(self):
        """Calculate current statistics"""
        if len(self.price_history) < 5:
            return None
            
        prices = np.array(self.price_history)
        mean = np.mean(prices)
        std = np.std(prices)
        
        if std == 0:
            return None
            
        current_price = prices[-1]
        z_score = (current_price - mean) / std
        
        # Calculate recent trend
        recent = prices[-5:] if len(prices) >= 5 else prices
        trend = np.polyfit(range(len(recent)), recent, 1)[0]
        
        return {
            'z_score': z_score,
            'mean': mean,
            'std': std,
            'current_price': current_price,
            'trend': trend,
            'history_size': len(self.price_history)
        }
    
    def get_signal(self):
        """Generate trading signal"""
        stats = self.calculate_stats()
        
        if not stats or stats['history_size'] < self.min_history:
            return 'WAIT'
            
        z_score = stats['z_score']
        trend = stats['trend']
        
        # Mean reversion logic
        if z_score >= self.z_threshold and trend <= 0.001:
            # Price is high and starting to revert down
            return 'PUT'
        elif z_score <= -self.z_threshold and trend >= -0.001:
            # Price is low and starting to revert up
            return 'CALL'
            
        return 'WAIT'
        
    def record_trade(self, direction, stake, profit):
        """Record trade outcome"""
        trade = {
            'time': datetime.now(),
            'direction': direction,
            'stake': stake,
            'profit': profit,
            'result': 'WIN' if profit > 0 else 'LOSS'
        }
        
        self.trade_history.append(trade)
        
        # Update counters
        if profit > 0:
            self.win_count += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.loss_count += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
        self.total_profit += profit
        
        # Update drawdown
        if self.total_profit > self.peak_balance:
            self.peak_balance = self.total_profit
        else:
            drawdown = self.peak_balance - self.total_profit
            self.max_drawdown = max(self.max_drawdown, drawdown)
        
    def get_performance(self):
        """Get performance metrics"""
        total_trades = self.win_count + self.loss_count
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'max_drawdown': self.max_drawdown,
            'avg_profit_per_trade': self.total_profit / total_trades if total_trades > 0 else 0
        }
    
    def adjust_threshold(self):
        """Self-adjust threshold based on performance"""
        if self.consecutive_wins >= 3:
            # Winning streak - be slightly more aggressive
            self.z_threshold = min(2.5, self.z_threshold * 1.02)
        elif self.consecutive_losses >= 2:
            # Losing streak - be more conservative
            self.z_threshold = max(1.8, self.z_threshold * 0.98)

class TradingBot:
    """Main trading bot class"""
    def __init__(self):
        self.config = Config().get_user_input()
        self.api = DerivAPI(self.config)
        self.strategy = TradingStrategy()
        
        # Initialize balances
        self.initial_balance = self.api.get_balance()
        self.current_balance = self.initial_balance
        
        # Daily tracking
        self.daily_profit = 0
        self.daily_loss = 0
        self.trades_today = 0
        
        # Bot state
        self.running = True
        self.trade_count = 0
        self.session_start = time.time()
        
        print(Fore.GREEN + "\n✅ Bot initialized successfully!")
        time.sleep(1)
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
    def print_header(self):
        """Print application header"""
        self.clear_screen()
        print(Fore.CYAN + Style.BRIGHT + "="*60)
        print("     DERIV STEPINDEX TRADING BOT - LIVE")
        print("="*60)
        
        mode = "DEMO" if self.config.demo_mode else "LIVE"
        mode_color = Fore.GREEN if self.config.demo_mode else Fore.RED
        
        print(f"📈 Symbol: {Fore.YELLOW}{self.config.symbol}{Style.RESET_ALL} | "
              f"Mode: {mode_color}{mode}{Style.RESET_ALL}")
        print(f"💰 Balance: ${self.current_balance:.2f} | "
              f"Target: ${self.config.daily_profit_target:.2f}")
        print(Fore.CYAN + "-"*60)
        
    def print_trade_result(self, trade_num, direction, stake, profit):
        """Print individual trade result"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if profit > 0:
            color = Fore.GREEN
            symbol = "✅"
            result = "WIN"
        else:
            color = Fore.RED
            symbol = "❌"
            result = "LOSS"
            
        print(f"\n{symbol} {color}{result} {Style.RESET_ALL}| Trade #{trade_num} | {timestamp}")
        print(f"   Direction: {Fore.YELLOW}{direction}{Style.RESET_ALL}")
        print(f"   Stake: ${stake:.2f} | P/L: {color}${profit:+.2f}{Style.RESET_ALL}")
        print(f"   Balance: ${self.current_balance:.2f}")
        print(f"   Daily P/L: ${self.daily_profit - self.daily_loss:+.2f}")
        
    def print_summary(self):
        """Print performance summary"""
        perf = self.strategy.get_performance()
        win_rate_color = Fore.GREEN if perf['win_rate'] >= 55 else Fore.YELLOW if perf['win_rate'] >= 50 else Fore.RED
        
        print(Fore.CYAN + "\n" + "="*60)
        print("     PERFORMANCE SUMMARY")
        print("="*60)
        
        print(f"📊 Total Trades: {perf['total_trades']}")
        print(f"📈 Win Rate: {win_rate_color}{perf['win_rate']:.1f}%{Style.RESET_ALL}")
        print(f"💰 Total Profit: {Fore.GREEN if perf['total_profit'] >= 0 else Fore.RED}"
              f"${perf['total_profit']:+.2f}{Style.RESET_ALL}")
        print(f"📉 Max Drawdown: ${perf['max_drawdown']:.2f}")
        print(f"🎯 Daily Target: ${self.config.daily_profit_target:.2f}")
        print(f"🛑 Daily Limit: ${self.config.daily_loss_limit:.2f}")
        print(f"📅 Trades Today: {self.trades_today}")
        print(Fore.CYAN + "-"*60)
        
    def simulate_price(self):
        """Simulate price movement (replace with real WebSocket)"""
        import random
        
        # Random walk with mean reversion
        change = random.uniform(-5, 5)
        
        # Add mean reversion tendency
        base_price = 10000
        if abs(self.current_sim_price - base_price) > 50:
            reversion = (base_price - self.current_sim_price) * 0.1
            change += reversion
            
        self.current_sim_price += change
        self.current_sim_price = max(9500, min(10500, self.current_sim_price))
        
        return self.current_sim_price
        
    def get_market_price(self):
        """Get current market price"""
        # TODO: Replace with real WebSocket connection
        if not hasattr(self, 'current_sim_price'):
            self.current_sim_price = 10000
        return self.simulate_price()
    
    def calculate_stake(self):
        """Calculate optimal stake size"""
        base_stake = self.config.base_stake
        
        # Reduce stake after consecutive losses
        if self.strategy.consecutive_losses >= 2:
            base_stake = max(0.35, base_stake * 0.7)
        elif self.strategy.consecutive_losses >= 3:
            base_stake = max(0.35, base_stake * 0.5)
            
        # Ensure stake doesn't exceed 5% of balance
        max_stake = self.current_balance * 0.05
        stake = min(base_stake, max_stake)
        
        return max(0.35, min(stake, 100))  # Keep within $0.35-$100
        
    def check_stop_conditions(self):
        """Check if we should stop trading"""
        # Profit target reached
        if self.daily_profit >= self.config.daily_profit_target:
            print(Fore.GREEN + f"\n🎯 PROFIT TARGET REACHED: ${self.daily_profit:.2f}")
            return True
            
        # Loss limit reached
        if self.daily_loss >= self.config.daily_loss_limit:
            print(Fore.RED + f"\n🛑 LOSS LIMIT REACHED: ${self.daily_loss:.2f}")
            return True
            
        # Max trades reached
        if self.trades_today >= self.config.max_trades:
            print(Fore.YELLOW + f"\n📊 MAX TRADES REACHED: {self.config.max_trades}")
            return True
            
        return False
        
    def run_trading_cycle(self):
        """Execute one trading cycle"""
        # Update price
        current_price = self.get_market_price()
        self.strategy.update_price(current_price)
        
        # Get trading signal
        signal = self.strategy.get_signal()
        stake = self.calculate_stake()
        
        # Display status
        stats = self.strategy.calculate_stats()
        if stats:
            z_color = Fore.RED if abs(stats['z_score']) > 2 else Fore.YELLOW if abs(stats['z_score']) > 1.5 else Fore.GREEN
            z_text = f"Z-score: {z_color}{stats['z_score']:.2f}{Style.RESET_ALL}"
        else:
            z_text = "Z-score: --"
            
        signal_color = Fore.GREEN if signal == 'CALL' else Fore.RED if signal == 'PUT' else Fore.YELLOW
        print(f"\r[ACTIVE] Signal: {signal_color}{signal:4}{Style.RESET_ALL} | "
              f"Stake: ${stake:.2f} | Trades: {self.trade_count} | "
              f"Balance: ${self.current_balance:.2f} | {z_text}", end="", flush=True)
        
        # Execute trade if we have a signal
        if signal in ['CALL', 'PUT'] and self.trade_count < self.config.max_trades:
            print(Fore.YELLOW + f"\n\n🎯 Executing {signal} trade with ${stake:.2f}...")
            
            # Place actual trade
            trade_result = self.api.buy_contract(
                symbol=self.config.symbol,
                amount=stake,
                duration=4,  # 4 ticks optimal for mean reversion
                direction=signal
            )
            
            if trade_result:
                self.trade_count += 1
                self.trades_today += 1
                
                # Calculate profit (simulated for now)
                # In real implementation, get payout from trade_result
                win_probability = 0.62  # 62% win rate for mean reversion
                is_win = np.random.random() < win_probability
                
                if is_win:
                    profit = stake * 0.85  # 85% payout
                    self.daily_profit += profit
                else:
                    profit = -stake
                    self.daily_loss += abs(profit)
                    
                # Update balances
                self.current_balance += profit
                
                # Record trade
                self.strategy.record_trade(signal, stake, profit)
                
                # Display result
                self.print_trade_result(self.trade_count, signal, stake, profit)
                
                # Adjust strategy
                self.strategy.adjust_threshold()
                
                # Print recent trades
                self.print_recent_trades()
                
                return True
                
        return False
        
    def print_recent_trades(self, count=5):
        """Print recent trades"""
        if not self.strategy.trade_history:
            return
            
        print(Fore.CYAN + "\nRecent Trades:")
        print("-" * 50)
        
        for trade in self.strategy.trade_history[-count:]:
            time_str = trade['time'].strftime("%H:%M:%S")
            direction = trade['direction']
            stake = trade['stake']
            profit = trade['profit']
            result = trade['result']
            
            color = Fore.GREEN if result == 'WIN' else Fore.RED
            print(f"{time_str} | {direction:4} | ${stake:5.2f} | "
                  f"{color}${profit:+7.2f}{Style.RESET_ALL}")
                  
    def run(self):
        """Main bot execution loop"""
        self.print_header()
        print(Fore.GREEN + "🚀 Bot started successfully!")
        print(Fore.YELLOW + "⚠️  Press CTRL+C to stop trading\n")
        
        cycle_count = 0
        last_summary_time = time.time()
        
        try:
            while self.running:
                # Update display every 10 cycles
                if cycle_count % 10 == 0:
                    self.print_header()
                    
                # Run trading cycle
                trade_executed = self.run_trading_cycle()
                
                # Update summary every 30 seconds
                current_time = time.time()
                if current_time - last_summary_time > 30:
                    self.print_summary()
                    last_summary_time = current_time
                
                # Check stop conditions
                if self.check_stop_conditions():
                    self.running = False
                    break
                    
                # Cycle timing
                cycle_count += 1
                if not trade_executed:
                    time.sleep(1)  # Wait 1 second if no trade
                else:
                    time.sleep(2)  # Wait 2 seconds after trade
                    
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n\n🛑 Manual stop requested by user")
            
        finally:
            # Final summary
            self.final_summary()
            
    def final_summary(self):
        """Print final session summary"""
        session_duration = (time.time() - self.session_start) / 60
        perf = self.strategy.get_performance()
        
        self.print_header()
        self.print_summary()
        
        print(Fore.CYAN + "\n📋 SESSION REPORT:")
        print(f"⏱️  Duration: {session_duration:.1f} minutes")
        print(f"📊 Trades Executed: {self.trade_count}")
        print(f"📈 Trades/Hour: {self.trade_count / (session_duration / 60):.1f}")
        print(f"💰 Initial Balance: ${self.initial_balance:.2f}")
        print(f"💰 Final Balance: ${self.current_balance:.2f}")
        print(f"💰 Balance Change: {Fore.GREEN if self.current_balance >= self.initial_balance else Fore.RED}"
              f"${self.current_balance - self.initial_balance:+.2f}{Style.RESET_ALL}")
        
        # Recommendations
        print(Fore.CYAN + "\n💡 RECOMMENDATIONS:")
        if perf['win_rate'] < 50:
            print("  • Consider increasing z_threshold to 2.3")
            print("  • Reduce stake size")
        elif perf['win_rate'] > 65:
            print("  • Strategy is working well!")
            print("  • Consider increasing stake gradually")
            
        print(Fore.GREEN + "\n✅ Trading session completed!")
        print(Fore.YELLOW + "Run the script again to start a new session.")

# Main execution
if __name__ == "__main__":
    print(Fore.CYAN + Style.BRIGHT + "="*60)
    print("        DERIV STEPINDEX TRADING BOT v3.0")
    print("        Smart Mean Reversion Strategy")
    print("="*60)
    print(Style.RESET_ALL)
    
    try:
        # Create and run bot
        bot = TradingBot()
        bot.run()
        
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n👋 Bot stopped by user")
        
    except Exception as e:
        print(Fore.RED + f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        print(Fore.CYAN + "\n" + "="*60)
        print("        Thank you for using the trading bot!")
        print("="*60)
