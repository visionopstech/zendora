import io
import qrcode
from qrcode.image.pil import PilImage


class QRCodeService:
    """Service for generating QR codes."""
    
    @staticmethod
    def generate_qr_code(url: str) -> io.BytesIO:
        """
        Generate a QR code image for the given URL.
        
        Args:
            url: The URL to encode in the QR code
            
        Returns:
            BytesIO: In-memory PNG image buffer
        """
        # Create QR code instance with optimal settings
        qr = qrcode.QRCode(
            version=1,  # Auto-adjust size based on content
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction (30%)
            box_size=10,  # Size of each box in pixels
            border=4,  # Border size in boxes (minimum is 4)
        )
        
        # Add data and generate
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white", image_factory=PilImage)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
