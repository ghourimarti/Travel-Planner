{{/* Common naming + labels, plus the computed broker/DB URLs. */}}

{{- define "voyantra.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "voyantra.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "voyantra.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "voyantra.labels" -}}
app.kubernetes.io/name: {{ include "voyantra.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Per-component selector labels (component passed in as the second arg). */}}
{{- define "voyantra.selectorLabels" -}}
app.kubernetes.io/name: {{ include "voyantra.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* DATABASE_URL: in-cluster Postgres Service, or the external override. */}}
{{- define "voyantra.databaseUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql+asyncpg://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "voyantra.fullname" . }}-db:5432/{{ .Values.postgres.db }}
{{- else -}}
{{- required "externalDatabaseUrl is required when postgres.enabled=false" .Values.externalDatabaseUrl -}}
{{- end -}}
{{- end -}}

{{/* REDIS_URL: in-cluster Redis Service, or the external override. */}}
{{- define "voyantra.redisUrl" -}}
{{- if .Values.redis.enabled -}}
redis://{{ include "voyantra.fullname" . }}-redis:6379/0
{{- else -}}
{{- required "externalRedisUrl is required when redis.enabled=false" .Values.externalRedisUrl -}}
{{- end -}}
{{- end -}}
