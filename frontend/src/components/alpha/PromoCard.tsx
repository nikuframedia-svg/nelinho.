interface PromoCardProps {
  title?: string;
  subtitle?: string;
  imageUrl?: string;
  buttonText?: string;
  onButtonClick?: () => void;
}

export function PromoCard({
  title = 'Streamline Your Shipping',
  subtitle = '24/7 support, always here when you need us.',
  imageUrl = 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=400&h=200&fit=crop',
  buttonText = 'Get Started Now',
  onButtonClick,
}: PromoCardProps) {
  return (
    <div className="alpha-promo-card">
      <h3 className="alpha-promo-title">{title}</h3>
      <p className="alpha-promo-subtitle">{subtitle}</p>
      
      <img 
        src={imageUrl} 
        alt="Shipping containers" 
        className="alpha-promo-image"
      />

      <button 
        className="alpha-btn-cta"
        onClick={onButtonClick}
      >
        {buttonText}
      </button>
    </div>
  );
}







