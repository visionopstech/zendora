from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Optional
import os

from app.core.config import settings
from app.models.user import User
from app.models.gift_collection import GiftCollection
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
    
    async def send_family_admin_credentials_email(
        self,
        family_admin: User,
        password: str
    ) -> bool:
        """
        Send credentials email to a newly created family admin.
        
        Triggered when: a director creates a gift collection for a new family.
        """
        template = jinja_env.get_template('family_admin_credentials.html')
        
        html_content = template.render(
            family_admin_name=family_admin.full_name or 'there',
            family_admin_email=family_admin.email,
            password=password,
            login_url=f"{settings.frontend_url}/login"
        )
        
        return await self.send_email(
            to_email=family_admin.email,
            subject="Welcome to Zendora - Your Family Admin Credentials",
            html_content=html_content
        )
    
    async def send_gift_collection_published_email(
        self,
        gift_collection: GiftCollection,
        director: User
    ) -> bool:
        """
        Notify the director when a family admin publishes a gift collection.
        """
        template = jinja_env.get_template('gift_collection_published.html')
        
        html_content = template.render(
            director_name=director.full_name or 'Director',
            collection_title=gift_collection.title or 'Untitled Gift Collection',
            collection_url=f"{settings.frontend_url}/w/{gift_collection.public_slug}",
            family_admin_email=(
                gift_collection.family_admin.email if gift_collection.family_admin else 'Unknown'
            )
        )
        
        return await self.send_email(
            to_email=director.email,
            subject=f"Gift Collection Published: {gift_collection.title or 'Untitled'}",
            html_content=html_content
        )
    
    async def send_purchase_confirmation_emails(
        self,
        order: Order
    ) -> tuple[bool, bool]:
        """
        Send purchase confirmation emails to the family admin and the director.
        
        Triggered when: a visitor completes a purchase (Stripe webhook).
        
        Returns:
            tuple[bool, bool]: (family_admin_sent, director_sent)
        """
        template = jinja_env.get_template('purchase_confirmation.html')
        
        products = []
        for order_product in order.products:
            products.append({
                'name': order_product.product_name,
                'price': float(order_product.product_price),
                'quantity': order_product.quantity,
                'total': float(order_product.product_price * order_product.quantity)
            })
        
        collection_title = order.gift_collection.title or 'Gift Collection'
        
        family_admin_html = template.render(
            recipient_name=order.family_admin.full_name or 'there',
            recipient_type='family_admin',
            visitor_name=order.visitor.full_name or order.visitor.email,
            visitor_email=order.visitor.email,
            collection_title=collection_title,
            products=products,
            total_amount=float(order.total_amount),
            order_id=str(order.id),
            order_date=order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else 'N/A'
        )
        
        family_admin_sent = await self.send_email(
            to_email=order.family_admin.email,
            subject="New Purchase on Your Gift Collection",
            html_content=family_admin_html
        )
        
        director = order.gift_collection.director
        director_html = template.render(
            recipient_name=director.full_name or 'Director',
            recipient_type='director',
            visitor_name=order.visitor.full_name or order.visitor.email,
            visitor_email=order.visitor.email,
            collection_title=collection_title,
            family_admin_email=order.family_admin.email,
            products=products,
            total_amount=float(order.total_amount),
            order_id=str(order.id),
            order_date=order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else 'N/A'
        )
        
        director_sent = await self.send_email(
            to_email=director.email,
            subject=f"Purchase Notification: {collection_title}",
            html_content=director_html
        )
        
        return family_admin_sent, director_sent
