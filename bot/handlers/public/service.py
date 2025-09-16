from backend.src.common.enums import UserRole
from bot.constants import ROLE_COMMANDS, ROLE_EMOJI_MAP
from bot.messages import CommonMessages, PublicMessages


def generate_help_text(role: UserRole) -> str:
    """
    Генерирует текст справки по командам в зависимости от роли.
    """
    lines = [
        PublicMessages.HELP_HEADER,
        PublicMessages.MAIN_COMMANDS,
        PublicMessages.HELP_COMMAND,
    ]
    if role != UserRole.GUEST:
        lines.append(PublicMessages.ME_COMMAND)

    role_config = ROLE_COMMANDS.get(role)
    if role_config:
        lines.append(f"\n{role_config['icon']} {role_config['title']}")
        lines.extend(cmd.strip() for cmd in role_config["commands"])
    return "\n".join(lines)


def get_user_status_text(user_data: dict) -> str:
    """
    Генерирует текст со статусом и ролью пользователя.
    """
    role = user_data.get("role", UserRole.GUEST)
    is_authorized = role != UserRole.GUEST
    status = PublicMessages.AUTHORIZED if is_authorized else PublicMessages.UNAUTHORIZED

    # Безопасное получение эмодзи и имени роли
    emoji = ROLE_EMOJI_MAP.get(role, PublicMessages.DEFAULT_EMOJI)
    role_name = role.value.upper() if isinstance(role, UserRole) else str(role).upper()

    return CommonMessages.STATUS_TEMPLATE.format(status=status, emoji=emoji, role_name=role_name)
