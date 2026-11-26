const ENTRY_CODE_MESSAGES = {
  unbalanced_entry:
    'La póliza está descuadrada. La suma de cargos debe ser igual a la suma de abonos.',
  period_closed:
    'El periodo fiscal está cerrado. No se pueden registrar ni modificar pólizas.',
  entry_date_out_of_period:
    'La fecha de la póliza debe pertenecer al mes y año del periodo fiscal.',
  non_selectable_account:
    'La cuenta seleccionada es acumulativa. Elige una cuenta afectable.',
  invalid_line_amounts:
    'Cada renglón debe capturar un solo importe mayor a cero, en cargo o en abono.',
  invalid_fiscal_period:
    'El periodo fiscal no pertenece a la empresa activa.',
  invalid_document:
    'El documento vinculado no pertenece a la empresa activa.',
  validation_error:
    'Revisa los datos de la póliza. Hay campos incompletos o inválidos.',
  error: 'No fue posible guardar la póliza.',
}

const PERIOD_CODE_MESSAGES = {
  draft_entries_pending:
    'No se puede cerrar el periodo: existen pólizas en borrador pendientes.',
  period_already_closed: 'El periodo fiscal ya se encuentra cerrado.',
  period_already_open: 'El periodo fiscal ya se encuentra abierto.',
  min_length: 'La justificación debe tener al menos 15 caracteres.',
  validation_error: 'Revisa la información capturada e inténtalo nuevamente.',
  error: 'No fue posible completar la operación.',
}

function uniqueMessages(messages) {
  return [...new Set(messages.filter(Boolean))]
}

function mapApiError(error, codeMessages, fallbackCode) {
  const sourceErrors = Array.isArray(error?.errors) ? error.errors : []
  const mapped = sourceErrors.map((item) => {
    const code = item?.code || error?.code || fallbackCode
    return {
      field: item?.field || null,
      code,
      message:
        codeMessages[code] ||
        item?.message ||
        error?.message ||
        codeMessages[fallbackCode] ||
        '',
    }
  })

  if (mapped.length === 0) {
    const code = error?.code || fallbackCode
    mapped.push({
      field: null,
      code,
      message:
        codeMessages[code] ||
        error?.message ||
        codeMessages[fallbackCode] ||
        '',
    })
  }

  const fieldErrors = {}
  const general = []

  mapped.forEach((item) => {
    if (item.field && item.field !== 'items' && item.field !== 'non_field_errors') {
      if (!fieldErrors[item.field]) fieldErrors[item.field] = item.message
    } else {
      general.push(item.message)
    }
  })

  const messages = uniqueMessages(general.length ? general : mapped.map((item) => item.message))

  return {
    code: error?.code || mapped[0]?.code || fallbackCode,
    errors: mapped,
    fieldErrors,
    messages,
    message: messages[0] || '',
  }
}

/** Traduce los códigos de error de la API de pólizas a mensajes del formulario. */
export function mapEntryApiError(error) {
  return mapApiError(error, ENTRY_CODE_MESSAGES, 'error')
}

/** Traduce los errores de cierre y reapertura de periodos. */
export function mapPeriodApiError(error) {
  return mapApiError(error, PERIOD_CODE_MESSAGES, 'error')
}
