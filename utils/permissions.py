from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    role_name = ""

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and user.is_authenticated and role and role.name == self.role_name)


class IsSuperAdmin(RolePermission):
    role_name = "super_admin"


class IsCompanyAdmin(RolePermission):
    role_name = "company_admin"


class IsAgent(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        role = getattr(getattr(user, "role", None), "name", None)
        return bool(user and user.is_authenticated and role in {"agent_guichet", "controleur"})


class IsAgentGuichet(RolePermission):
    role_name = "agent_guichet"


class IsControleur(RolePermission):
    role_name = "controleur"


class IsVoyageur(RolePermission):
    role_name = "voyageur"
