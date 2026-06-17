import secrets
import string

from django.core.exceptions import ValidationError

from utils.sms import send_sms

from .models import Role, User


def create_voyageur(data: dict) -> User:
    """Create a traveler account.

    Args:
        data: Validated user registration data.

    Returns:
        Created user with the voyageur role.

    Raises:
        ValidationError: If the phone number is already used.
    """
    phone = data.get("phone", "").strip()
    if User.objects.filter(phone=phone).exists():
        raise ValidationError({"phone": "Ce numero de telephone est deja utilise."})

    role, _ = Role.objects.get_or_create(name=Role.RoleName.VOYAGEUR)
    user = User(
        prenom=data["prenom"],
        nom=data["nom"],
        email=data.get("email") or None,
        phone=phone,
        role=role,
    )
    user.set_password(data["password"])
    user.full_clean(exclude=["password"])
    user.save()
    return user


def send_temp_password_sms(agent: User) -> str:
    """Generate and send a temporary password to an agent by SMS.

    Args:
        agent: Agent user receiving the temporary password.

    Returns:
        The generated temporary password.

    Raises:
        ValidationError: If the user does not have a phone number.
    """
    if not agent.phone:
        raise ValidationError({"phone": "Le telephone de l'agent est obligatoire."})

    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(8))
    agent.set_password(temp_password)
    agent.save(update_fields=["password", "updated_at"])
    send_sms(agent.phone, f"Votre mot de passe temporaire TransBooking BF: {temp_password}")
    return temp_password
