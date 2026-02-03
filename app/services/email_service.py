from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Optional
import os

from app.core.config import settings
from app.models.user import User
from app.models.wishlist import Wishlist
from app.models.order import Order


# Initialize Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'emails')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    """Service for sending emails via SendGrid."""
    
    def __init__(self):
        self.sg = SendGridAPIClient(settings.sendgrid_api_key)
        self.from_email = Email(settings.sendgrid_from_email)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SendGrid.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content
            plain_content: Plain text content (optional)
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            message = Mail(
                from_email=self.from_email,
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            if plain_content:
                message.add_content(Content("text/plain", plain_content))
            
            response = self.sg.send(message)
            
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    async def send_admin_credentials_email(
        self,
        admin: User,
        password: str
    ) -> bool:
        """
        Send credentials email to newly created admin.
        
        Triggered when: Manager creates a wishlist and assigns a new admin.
        """
        template = jinja_env.get_template('admin_credentials.html')
        
        html_content = template.render(
            admin_name=admin.full_name or 'Admin',
            admin_email=admin.email,
            password=password,
            login_url=f"{settings.frontend_url}/login"
        )
        
        return await self.send_email(
            to_email=admin.email,
            subject="Welcome to Zendora - Your Admin Credentials",
            html_content=html_content
        )
    
    async def send_wishlist_published_email(
        self,
        wishlist: Wishlist,
        manager: User
    ) -> bool:
        """
        Send notification email to manager when admin publishes wishlist.
        
        Triggered when: Admin publishes their wishlist.
        """
        template = jinja_env.get_template('wishlist_published.html')
        
        html_content = template.render(
            manager_name=manager.full_name or 'Manager',
            wishlist_title=wishlist.title or 'Untitled Wishlist',
            wishlist_url=f"{settings.frontend_url}/w/{wishlist.public_slug}",
            admin_email=wishlist.admin.email if wishlist.admin else 'Unknown'
        )
        
        return await self.send_email(
            to_email=manager.email,
            subject=f"Wishlist Published: {wishlist.title or 'Untitled'}",
            html_content=html_content
        )
    
    async def send_purchase_confirmation_emails(
        self,
        order: Order
    ) -> tuple[bool, bool]:
        """
        Send purchase confirmation emails to admin and manager.
        
        Triggered when: Visitor completes a purchase (Stripe webhook).
        
        Returns:
            tuple[bool, bool]: (admin_sent, manager_sent)
        """
        template = jinja_env.get_template('purchase_confirmation.html')
        
        # Prepare order details
        products = []
        for order_product in order.products:
            products.append({
                'name': order_product.product_name,
                'price': float(order_product.product_price),
                'quantity': order_product.quantity,
                'total': float(order_product.product_price * order_product.quantity)
            })
        
        # Send to admin
        admin_html = template.render(
            recipient_name=order.admin.full_name or 'Admin',
            recipient_type='admin',
            visitor_name=order.visitor.full_name or order.visitor.email,
            visitor_email=order.visitor.email,
            wishlist_title=order.wishlist.title or 'Your Wishlist',
            products=products,
            total_amount=float(order.total_amount),
            order_id=str(order.id),
            order_date=order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else 'N/A'
        )
        
        admin_sent = await self.send_email(
            to_email=order.admin.email,
            subject=f"New Purchase on Your Wishlist!",
            html_content=admin_html
        )
        
        # Send to manager
        manager = order.wishlist.manager
        manager_html = template.render(
            recipient_name=manager.full_name or 'Manager',
            recipient_type='manager',
            visitor_name=order.visitor.full_name or order.visitor.email,
            visitor_email=order.visitor.email,
            wishlist_title=order.wishlist.title or 'Wishlist',
            admin_email=order.admin.email,
            products=products,
            total_amount=float(order.total_amount),
            order_id=str(order.id),
            order_date=order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else 'N/A'
        )
        
        manager_sent = await self.send_email(
            to_email=manager.email,
            subject=f"Purchase Notification: {order.wishlist.title or 'Wishlist'}",
            html_content=manager_html
        )
        
        return admin_sent, manager_sent
