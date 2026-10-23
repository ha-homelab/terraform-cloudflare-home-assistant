variable "account_id" {
  description = "Cloudflare account ID supplied by the private deployment root."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-f0-9]{32}$", var.account_id))
    error_message = "account_id must be a 32-character hexadecimal Cloudflare account ID."
  }
}

variable "zone_id" {
  description = "Cloudflare zone ID supplied by the private deployment root."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-f0-9]{32}$", var.zone_id))
    error_message = "zone_id must be a 32-character hexadecimal Cloudflare zone ID."
  }
}

variable "tunnel_id" {
  description = "Existing remotely managed tunnel UUID. No tunnel or connector credential is created."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", var.tunnel_id))
    error_message = "tunnel_id must be an existing tunnel UUID."
  }
}

variable "hostname" {
  description = "Fully qualified Home Assistant hostname; no deployment domain is included in this module."
  type        = string
  nullable    = false
  validation {
    condition = length(var.hostname) <= 253 && length(split(".", var.hostname)) > 1 && alltrue([
      for label in split(".", var.hostname) : can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", label))
    ])
    error_message = "hostname must be a lowercase DNS name without wildcard, scheme, port or path."
  }
}

variable "origin_service" {
  description = "HTTP(S) origin reachable from cloudflared, including its actual port; no credentials or URL path."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^https?://([a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?|\\[[0-9a-fA-F:]+\\])(:[0-9]{1,5})?$", var.origin_service))
    error_message = "origin_service must be an HTTP(S) authority without credentials, query, fragment or path."
  }
  validation {
    condition = alltrue([
      for port in regexall(":([0-9]+)$", var.origin_service) : tonumber(port[0]) >= 1 && tonumber(port[0]) <= 65535
    ])
    error_message = "origin_service port must be between 1 and 65535."
  }
  validation {
    condition = alltrue([
      for host in regexall("\\[([^]]+)\\]", var.origin_service) : can(cidrhost("${host[0]}/128", 0))
    ])
    error_message = "A bracketed origin_service host must be a valid IPv6 address."
  }
  validation {
    condition = alltrue([
      for host in regexall("^https?://([a-zA-Z0-9.-]+)(:[0-9]+)?$", var.origin_service) :
      length(host[0]) <= 253 && alltrue([
        for label in split(".", host[0]) : can(regex("^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$", label))
      ])
    ])
    error_message = "origin_service must use valid DNS labels or a bracketed IPv6 address."
  }
}

variable "dns_comment" {
  description = "Optional DNS comment. Do not put secrets or personal data in resource metadata."
  type        = string
  default     = null
}

variable "callback_access" {
  description = "Optional existing policies for the HTML5 notification callback only. Null creates no Access application; this never protects the entire HA UI."
  type = object({
    name                       = optional(string, "home-assistant-notification-callback")
    policy_ids                 = list(string)
    session_duration           = optional(string, "24h")
    auto_redirect_to_identity  = optional(bool, false)
    enable_binding_cookie      = optional(bool, false)
    options_preflight_bypass   = optional(bool, false)
    http_only_cookie_attribute = optional(bool, false)
  })
  default = null
  validation {
    condition = var.callback_access == null ? true : (
      length(var.callback_access.policy_ids) > 0 && length(distinct(var.callback_access.policy_ids)) == length(var.callback_access.policy_ids) && alltrue([
        for id in var.callback_access.policy_ids : can(regex("^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", id))
      ])
    )
    error_message = "callback_access requires at least one explicit existing policy UUID with no duplicates."
  }
}
