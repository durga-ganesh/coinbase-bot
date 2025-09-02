"""
CLI Commands for Coinbase Trading Bot
"""

import os
import sys
import click
import json
from datetime import datetime, timedelta
from typing import Optional

# Rich imports for clean CLI
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from rich import box

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.client import CoinbaseClient
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.strategies.rsi_strategy import RSIStrategy
from src.strategies.volatility_breakout import VolatilityBreakoutStrategy
from src.utils.config import load_config
from src.utils.logger import get_logger
from src.utils.exceptions import TradingError, APIError

logger = get_logger(__name__)
console = Console()

# Custom Click classes to add -h support
class CustomCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add -h as an alias for --help
        for param in self.params:
            if param.name == 'help' and isinstance(param, click.Option):
                if '-h' not in param.opts:
                    param.opts.append('-h')

class CustomGroup(click.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add -h as an alias for --help
        for param in self.params:
            if param.name == 'help' and isinstance(param, click.Option):
                if '-h' not in param.opts:
                    param.opts.append('-h')


def load_environment():
    """Load environment variables from .env file"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("[ENV  ] python-dotenv not installed, using system environment variables")


@click.group(cls=CustomGroup, context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """🚀 Coinbase Crypto Trading Bot"""
    load_environment()
    ctx.ensure_object(dict)
    
    # Show minimal banner only when running commands, not help
    if ctx.invoked_subcommand is not None:
        banner = Panel.fit(
            "[bold cyan]🚀 Coinbase Trading Bot[/bold cyan]",
            box=box.SIMPLE,
            border_style="cyan"
        )
        console.print(banner)
    
    # Load configuration
    try:
        ctx.obj['config'] = load_config(config)
        logger.info("[BOT  ] Configuration loaded successfully")
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)


@cli.command(cls=CustomCommand, context_settings=dict(help_option_names=['-h', '--help']))
@click.pass_context
def balance(ctx):
    """💰 Get account balances"""
    logger.info("[OPER ] Getting account balances")
    
    try:
        client = CoinbaseClient(ctx.obj['config'])
        accounts = client.get_accounts()
        
        # Create minimal balance display
        balance_text = "[bold]Account Balances[/bold]\n\n"
        total_usd = 0
        
        for account in accounts:
            currency = account.get('currency', 'Unknown')
            balance = account.get('available_balance', {})
            amount = float(balance.get('value', 0))
            
            if amount > 0.001:  # Only show non-zero balances
                usd_value = 0
                
                # Convert to USD for total
                if currency == 'USD':
                    usd_value = amount
                    total_usd += amount
                elif currency in ['BTC', 'ETH']:
                    try:
                        price = client.get_current_price(f"{currency}-USD")
                        usd_value = amount * price
                        total_usd += usd_value
                    except:
                        pass
                
                usd_str = f" [dim]([yellow]${usd_value:.2f}[/yellow])[/dim]" if usd_value > 0 else ""
                balance_text += f"[cyan]{currency}[/cyan]: {amount:.6f}{usd_str}\n"
        
        balance_text += f"\n[bold green]Total: ${total_usd:.2f}[/bold green]"
        
        panel = Panel(
            balance_text,
            box=box.SIMPLE,
            border_style="green"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(cls=CustomCommand)
@click.argument('product_id')
@click.pass_context
def price(ctx, product_id):
    """📈 Get current price and 24h stats"""
    logger.info(f"[OPER ] Getting price information for {product_id.upper()}")
    
    try:
        client = CoinbaseClient(ctx.obj['config'])
        current_price = client.get_current_price(product_id.upper())
        
        price_text = f"[bold cyan]{product_id.upper()}[/bold cyan]\n\n"
        price_text += f"[bold]Current Price:[/bold] [yellow]${current_price:.2f}[/yellow]\n"
        
        # Skip market data for now due to granularity API issue
        # TODO: Fix granularity parameter for Advanced Trade API
        price_text += "[dim]Historical data temporarily unavailable[/dim]"
        
        panel = Panel(
            price_text,
            box=box.SIMPLE,
            border_style="yellow"
        )
        console.print(panel)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(cls=CustomCommand)
@click.argument('product_id')
@click.argument('amount', type=float)
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def buy(ctx, product_id, amount, dry_run):
    """💰 Buy cryptocurrency (amount in USD)"""
    action_type = "Simulating" if dry_run else "Executing"
    logger.info(f"[OPER ] {action_type} buy order: ${amount} of {product_id.upper()}")
    
    try:
        client = CoinbaseClient(ctx.obj['config'])
        product_id = product_id.upper()
        
        # Get current price for confirmation
        current_price = client.get_current_price(product_id)
        estimated_quantity = amount / current_price
        
        order_text = f"[bold]Buy Order[/bold]\n\n"
        order_text += f"[bold]Product:[/bold] [cyan]{product_id}[/cyan]\n"
        order_text += f"[bold]Amount:[/bold] [yellow]${amount:.2f}[/yellow]\n"
        order_text += f"[bold]Price:[/bold] [blue]${current_price:.2f}[/blue]\n"
        order_text += f"[bold]Quantity:[/bold] [green]{estimated_quantity:.8f}[/green]"
        
        if dry_run:
            order_text += "\n\n[yellow]🔍 DRY RUN MODE[/yellow]"
        
        panel = Panel(
            order_text,
            box=box.SIMPLE,
            border_style="green"
        )
        console.print(panel)
        
        if dry_run:
            console.print("[yellow]DRY RUN - No order placed[/yellow]")
            return
        
        if not Confirm.ask(f"Confirm buy ${amount:.2f} of {product_id}?"):
            console.print("[red]Cancelled[/red]")
            return
        
        # Place the order
        result = client.place_market_buy_order(product_id, amount)
        console.print(f"[green]✓ Order placed: {result.get('order_id', 'N/A')[:8]}...[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(cls=CustomCommand)
@click.argument('product_id')
@click.argument('quantity', type=float)
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def sell(ctx, product_id, quantity, dry_run):
    """💸 Sell cryptocurrency (quantity in base currency)"""
    action_type = "Simulating" if dry_run else "Executing" 
    logger.info(f"[OPER ] {action_type} sell order: {quantity} {product_id.upper()}")
    
    try:
        client = CoinbaseClient(ctx.obj['config'])
        product_id = product_id.upper()
        
        # Get current price for confirmation
        current_price = client.get_current_price(product_id)
        estimated_value = quantity * current_price
        
        order_text = f"[bold]Sell Order[/bold]\n\n"
        order_text += f"[bold]Product:[/bold] [cyan]{product_id}[/cyan]\n"
        order_text += f"[bold]Quantity:[/bold] {quantity:.8f}\n"
        order_text += f"[bold]Price:[/bold] [blue]${current_price:.2f}[/blue]\n"
        order_text += f"[bold]Value:[/bold] [yellow]${estimated_value:.2f}[/yellow]"
        
        if dry_run:
            order_text += "\n\n[yellow]🔍 DRY RUN MODE[/yellow]"
        
        panel = Panel(
            order_text,
            box=box.SIMPLE,
            border_style="red"
        )
        console.print(panel)
        
        if dry_run:
            console.print("[yellow]DRY RUN - No order placed[/yellow]")
            return
        
        if not Confirm.ask(f"Confirm sell {quantity:.8f} {product_id}?"):
            console.print("[red]Cancelled[/red]")
            return
        
        # Place the order
        result = client.place_market_sell_order(product_id, quantity)
        console.print(f"[green]✓ Order placed: {result.get('order_id', 'N/A')[:8]}...[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.group(cls=CustomGroup)
def strategy():
    """⚡ Strategy management commands"""
    pass


@strategy.command('list', cls=CustomCommand)
@click.pass_context
def list_strategies(ctx):
    """📋 List available strategies"""
    strategies = {
        'sma_crossover': 'SMA Crossover',
        'rsi_strategy': 'RSI Strategy',
        'volatility_breakout': 'Volatility Breakout'
    }
    
    strategy_text = "[bold]Available Strategies[/bold]\n\n"
    for name, description in strategies.items():
        strategy_text += f"[cyan]{name}[/cyan]: {description}\n"
    
    # Show configured strategies
    config = ctx.obj['config']
    if config.strategies:
        strategy_text += "\n[bold]Configured[/bold]\n"
        for name, params in config.strategies.items():
            strategy_text += f"[green]{name}[/green]: {params}\n"
    
    panel = Panel(
        strategy_text,
        box=box.SIMPLE,
        border_style="magenta"
    )
    console.print(panel)


@strategy.command('run')
@click.argument('strategy_name')
@click.argument('product_id')
@click.option('--amount', type=float, default=100, help='Trade amount in USD')
@click.option('--dry-run', is_flag=True, help='Show signals without trading')
@click.pass_context
def run_strategy(ctx, strategy_name, product_id, amount, dry_run):
    """Run a trading strategy"""
    try:
        client = CoinbaseClient(ctx.obj['config'])
        config = ctx.obj['config']
        product_id = product_id.upper()
        
        # Create strategy instance
        strategy_config = config.get_strategy_config(strategy_name)
        
        if strategy_name == 'sma_crossover':
            strategy = SMACrossoverStrategy(**strategy_config)
        elif strategy_name == 'rsi_strategy':
            strategy = RSIStrategy(**strategy_config)
        elif strategy_name == 'volatility_breakout':
            strategy = VolatilityBreakoutStrategy(**strategy_config)
        else:
            click.echo(f"Unknown strategy: {strategy_name}")
            return
        
        click.echo(f"\n=== Running {strategy.name} ===")
        click.echo(f"Product: {product_id}")
        click.echo(f"Amount: ${amount}")
        
        # Get market data
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)  # 30 days of data
        
        market_data = client.get_market_data(
            product_id,
            granularity='SIXTY_MINUTE',  # Try different format
            start=start_time.isoformat(),
            end=end_time.isoformat()
        )
        
        if market_data.empty:
            click.echo("No market data available")
            return
        
        # Initialize strategy
        strategy.initialize(market_data)
        
        # Generate signal
        signal = strategy.generate_signal(market_data)
        
        click.echo(f"\nSignal: {signal.signal.value}")
        click.echo(f"Confidence: {signal.confidence:.2f}")
        click.echo(f"Price: ${signal.price:.2f}")
        
        if signal.metadata:
            click.echo("\nIndicators:")
            for key, value in signal.metadata.items():
                if isinstance(value, float):
                    click.echo(f"  {key}: {value:.4f}")
                else:
                    click.echo(f"  {key}: {value}")
        
        # Execute trade if signal is strong enough
        if signal.signal.value != 'HOLD' and signal.confidence > 0.5:
            if dry_run:
                click.echo(f"\n[DRY RUN] Would execute {signal.signal.value} order")
            else:
                if click.confirm(f"\nExecute {signal.signal.value} order with confidence {signal.confidence:.2f}?"):
                    try:
                        if signal.signal.value == 'BUY':
                            result = client.place_market_buy_order(product_id, amount)
                            click.echo(f"✅ Buy order placed: {result.get('order_id')}")
                        else:
                            # For sell, need to calculate quantity from amount
                            quantity = amount / signal.price
                            result = client.place_market_sell_order(product_id, quantity)
                            click.echo(f"✅ Sell order placed: {result.get('order_id')}")
                    except Exception as e:
                        click.echo(f"❌ Order failed: {e}")
                        
    except Exception as e:
        click.echo(f"Error running strategy: {e}")


@cli.command(cls=CustomCommand)
@click.argument('product_id')
@click.option('--days', type=int, default=30, help='Number of days of history')
@click.pass_context
def orders(ctx, product_id, days):
    """📊 Get order history"""
    product_display = product_id.upper() if product_id else "all products"
    logger.info(f"[OPER ] Getting order history for {product_display}")
    
    try:
        client = CoinbaseClient(ctx.obj['config'])
        orders = client.get_orders(product_id.upper() if product_id else None)
        
        orders_text = f"[bold]Order History[/bold]\n\n"
        
        if not orders:
            orders_text += "[dim]No orders found[/dim]"
        else:
            for order in orders[:10]:  # Show last 10 orders
                order_id = order.get('order_id', 'N/A')[:8]
                side = order.get('side', 'N/A')
                status = order.get('status', 'N/A')
                product = order.get('product_id', 'N/A')
                
                side_color = "green" if side == "BUY" else "red"
                orders_text += f"{order_id}... | [{side_color}]{side}[/{side_color}] | {status} | [cyan]{product}[/cyan]\n"
        
        panel = Panel(
            orders_text,
            box=box.SIMPLE,
            border_style="blue"
        )
        console.print(panel)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(cls=CustomCommand)
@click.pass_context
def health(ctx):
    """🏥 Check system health"""
    logger.info("[OPER ] Running system health check")
    
    try:
        health_text = "[bold]System Health[/bold]\n\n"
        
        # Check API connection
        try:
            client = CoinbaseClient(ctx.obj['config'])
            if client.health_check():
                health_text += "[green]✓[/green] API: Connected\n"
            else:
                health_text += "[red]✗[/red] API: Failed\n"
        except Exception as e:
            health_text += "[red]✗[/red] API: Error\n"
        
        # Check configuration
        config = ctx.obj['config']
        health_text += f"[green]✓[/green] Config: Loaded ({len(config.strategies)} strategies)\n"
        
        # Check environment variables (updated for JSON key file authentication)
        required_env = ['COINBASE_API_KEY_FILE']
        missing_env = [env for env in required_env if not os.getenv(env)]
        
        if missing_env:
            health_text += "[red]✗[/red] Environment: Missing vars\n"
        else:
            # Also check if the JSON key file actually exists
            json_key_file = os.getenv('COINBASE_API_KEY_FILE')
            if json_key_file and os.path.exists(json_key_file):
                health_text += "[green]✓[/green] Environment: Complete\n"
            elif json_key_file and not os.path.exists(json_key_file):
                health_text += "[red]✗[/red] Environment: Key file not found\n"
            else:
                health_text += "[red]✗[/red] Environment: Missing vars\n"
        
        # Sandbox mode
        sandbox_mode = os.getenv('COINBASE_SANDBOX', 'true').lower() == 'true'
        mode_text = "[yellow]Sandbox[/yellow]" if sandbox_mode else "[red]Live[/red]"
        health_text += f"Mode: {mode_text}"
        
        panel = Panel(
            health_text,
            box=box.SIMPLE,
            border_style="blue"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def main():
    """Main entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
