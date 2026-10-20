"""Restricted email wrappers: substitutions only, no loops, calls, or attributes."""

from jinja2 import StrictUndefined, nodes
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from cold_mailer.domain.models import ValidationError


def render_template(template_string: str, context: dict[str, str]) -> str:
    if len(template_string) > 20_000:
        raise ValidationError("Template exceeds 20,000 characters.")
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
    try:
        tree = environment.parse(template_string)
        allowed = (nodes.Template, nodes.Output, nodes.TemplateData, nodes.Name)
        if any(not isinstance(node, allowed) for node in tree.find_all(nodes.Node)):
            raise ValidationError("Wrappers support variable substitutions only.")
        result = environment.from_string(template_string).render(context)
        if len(result) > 100_000:
            raise ValidationError("Rendered body exceeds 100,000 characters.")
        return result
    except TemplateError:
        raise ValidationError("Template is invalid or refers to a missing field.") from None
