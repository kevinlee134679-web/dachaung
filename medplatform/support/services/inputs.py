from ...web.inputs import ID, Input, Version


class ServiceCreate(Input):
    service_draft_id: ID
    draft_revision: Version
    confirmation_ref_id: ID
    sharing_scope_ref_id: ID
