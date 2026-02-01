"""
Google Antigravity Manager - Lógica de Rotación Inteligente
Maneja la selección automática de cuentas basada en disponibilidad de cuotas.
"""

from datetime import datetime, timezone
from ..models import Account, Quota, Session, db


class RotationManager:
    """Gestiona la rotación inteligente de cuentas basada en estado de cuotas."""
    
    def __init__(self, user_id):
        self.user_id = user_id
    
    def get_available_accounts(self, provider=None):
        """
        Obtener todas las cuentas con cuotas disponibles.
        
        Args:
            provider: Filtrar por proveedor específico ('anthropic' o 'gemini')
            
        Returns:
            Lista de cuentas con cuotas disponibles
        """
        accounts = Account.query.filter_by(user_id=self.user_id).all()
        available = []
        
        for account in accounts:
            if provider == 'anthropic' and account.is_anthropic_available():
                available.append(account)
            elif provider == 'gemini' and account.is_gemini_available():
                available.append(account)
            elif provider is None:
                if account.is_anthropic_available() or account.is_gemini_available():
                    available.append(account)
        
        return available
    
    def get_best_account(self, prefer_anthropic=True):
        """
        Obtener la mejor cuenta disponible según prioridad.
        
        Args:
            prefer_anthropic: Si True, prioriza cuentas con Anthropic disponible
            
        Returns:
            Tupla de (account, provider) o (None, None) si no hay disponibles
        """
        # Prioridad 1: Cuenta con Anthropic disponible
        if prefer_anthropic:
            anthropic_accounts = self.get_available_accounts('anthropic')
            if anthropic_accounts:
                # Ordenar por menos usadas primero
                anthropic_accounts.sort(key=lambda a: a.veces_usada)
                return (anthropic_accounts[0], 'anthropic')
        
        # Prioridad 2: Cuenta con Gemini disponible
        gemini_accounts = self.get_available_accounts('gemini')
        if gemini_accounts:
            gemini_accounts.sort(key=lambda a: a.veces_usada)
            return (gemini_accounts[0], 'gemini')
        
        return (None, None)
    
    def get_active_session(self):
        """Obtener sesión activa actual si existe."""
        return Session.query.join(Account).filter(
            Account.user_id == self.user_id,
            Session.fin.is_(None)
        ).first()
    
    def start_session(self, account_id, provider):
        """
        Iniciar nueva sesión de trabajo.
        
        Args:
            account_id: ID de la cuenta a usar
            provider: Proveedor a usar ('anthropic' o 'gemini')
            
        Returns:
            Objeto Session creado
            
        Raises:
            ValueError: Si hay sesión activa o cuenta no válida
        """
        # Verificar si hay sesión activa
        active = self.get_active_session()
        if active:
            raise ValueError("Ya hay una sesión activa. Finalízala primero.")
        
        # Verificar cuenta
        account = Account.query.filter_by(id=account_id, user_id=self.user_id).first()
        if not account:
            raise ValueError("Cuenta no encontrada")
        
        # Verificar disponibilidad de cuota
        if provider == 'anthropic' and not account.is_anthropic_available():
            raise ValueError("Cuota de Anthropic agotada para esta cuenta")
        elif provider == 'gemini' and not account.is_gemini_available():
            raise ValueError("Cuota de Gemini agotada para esta cuenta")
        
        # Crear sesión
        session = Session(
            account_id=account_id,
            provider=provider,
            inicio=datetime.now(timezone.utc)
        )
        
        # Marcar cuenta como activa
        account.activa = True
        
        db.session.add(session)
        db.session.commit()
        
        return session
    
    def end_session(self, motivo='manual', proximo_reset=None):
        """
        Finalizar sesión activa.
        
        Args:
            motivo: 'manual' o 'cuota_agotada'
            proximo_reset: Timestamp del próximo reinicio si cuota agotada
            
        Returns:
            Objeto Session finalizada o None
        """
        session = self.get_active_session()
        if not session:
            return None
        
        session.end_session(motivo)
        
        # Si fue por cuota agotada, marcar la cuota
        if motivo == 'cuota_agotada' and proximo_reset:
            quota = Quota.query.filter_by(
                account_id=session.account_id,
                provider=session.provider
            ).first()
            
            if quota:
                quota.mark_exhausted(proximo_reset)
            else:
                # Crear cuota si no existe
                quota = Quota(
                    account_id=session.account_id,
                    provider=session.provider
                )
                db.session.add(quota)
                db.session.commit()
                quota.mark_exhausted(proximo_reset)
        
        db.session.commit()
        return session
    
    def rotate_to_next(self, motivo='cuota_agotada', proximo_reset=None, auto_start=True):
        """
        Rotar a la siguiente mejor cuenta disponible.
        
        Args:
            motivo: Motivo de la rotación
            proximo_reset: Tiempo de reinicio de la cuota actual
            auto_start: Si True, inicia sesión automáticamente con la nueva cuenta
            
        Returns:
            Dict con información de la rotación
        """
        # Finalizar sesión actual
        ended_session = self.end_session(motivo, proximo_reset)
        
        # Buscar siguiente mejor cuenta
        next_account, next_provider = self.get_best_account()
        
        result = {
            'ended_session': ended_session.to_dict() if ended_session else None,
            'next_account': next_account.to_dict() if next_account else None,
            'next_provider': next_provider,
            'rotated': False,
            'needs_user_choice': False
        }
        
        if not next_account:
            # No hay cuentas disponibles
            return result
        
        if next_provider == 'gemini':
            # Solo Gemini disponible, preguntar al usuario
            result['needs_user_choice'] = True
            result['next_anthropic_reset'] = self.get_next_anthropic_reset()
            return result
        
        if auto_start:
            # Iniciar nueva sesión automáticamente
            new_session = self.start_session(next_account.id, next_provider)
            result['new_session'] = new_session.to_dict()
            result['rotated'] = True
        
        return result
    
    def get_next_anthropic_reset(self):
        """Obtener el próximo tiempo de reinicio de Anthropic."""
        quota = Quota.query.join(Account).filter(
            Account.user_id == self.user_id,
            Quota.provider == 'anthropic',
            Quota.estado == 'agotada',
            Quota.proximo_reset.isnot(None)
        ).order_by(Quota.proximo_reset.asc()).first()
        
        if quota and quota.proximo_reset:
            return quota.proximo_reset.isoformat()
        return None
    
    def check_and_reset_quotas(self):
        """
        Verificar y reiniciar cuotas expiradas.
        
        Returns:
            Número de cuotas reiniciadas
        """
        expired_quotas = Quota.query.join(Account).filter(
            Account.user_id == self.user_id,
            Quota.estado == 'agotada',
            Quota.proximo_reset <= datetime.now(timezone.utc)
        ).all()
        
        count = 0
        for quota in expired_quotas:
            quota.reset()
            count += 1
        
        db.session.commit()
        return count
    
    def get_summary(self):
        """
        Obtener resumen de estado de cuentas.
        
        Returns:
            Dict con estadísticas de cuentas
        """
        # Use optimized query to avoid N+1 problem
        accounts = Account.get_all_with_rel(self.user_id)
        
        total = len(accounts)
        disponibles = 0
        limite_parcial = 0
        limite_total = 0
        
        horas_anthropic = 0
        horas_gemini = 0
        sesiones_anthropic = 0
        sesiones_gemini = 0
        
        # Contadores específicos por proveedor
        limite_anthropic = 0
        limite_gemini = 0
        
        for account in accounts:
            # Clasificación general
            classification = account.get_classification()
            if classification == 'disponible':
                disponibles += 1
            elif classification == 'limite_parcial':
                limite_parcial += 1
            else:
                limite_total += 1
            
            # Contadores específicos de agotamiento (independiente de si es parcial o total)
            if not account.is_anthropic_available():
                limite_anthropic += 1
            
            if not account.is_gemini_available():
                limite_gemini += 1
            
            # Contar sesiones por proveedor (filtrar en memoria)
            finished_sessions = [s for s in account.sessions if s.fin is not None]
            for session in finished_sessions:
                if session.duracion:
                    horas = session.duracion.total_seconds() / 3600
                    if session.provider == 'anthropic':
                        horas_anthropic += horas
                        sesiones_anthropic += 1
                    else:
                        horas_gemini += horas
                        sesiones_gemini += 1
        
        # Determinar modelo más usado
        modelo_mas_usado = None
        if sesiones_anthropic > sesiones_gemini:
            modelo_mas_usado = 'Anthropic'
        elif sesiones_gemini > sesiones_anthropic:
            modelo_mas_usado = 'Gemini'
        elif sesiones_anthropic > 0:
            modelo_mas_usado = 'Empate'
        
        return {
            'total': total,
            'disponibles': disponibles,
            'limite_parcial': limite_parcial,
            'limite_total': limite_total,
            'limite_anthropic': limite_anthropic,
            'limite_gemini': limite_gemini,
            'horas_por_modelo': {
                'anthropic': round(horas_anthropic, 2),
                'gemini': round(horas_gemini, 2)
            },
            'sesiones_por_modelo': {
                'anthropic': sesiones_anthropic,
                'gemini': sesiones_gemini
            },
            'modelo_mas_usado': modelo_mas_usado,
            'horas_totales': round(horas_anthropic + horas_gemini, 2)
        }
