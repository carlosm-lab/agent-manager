"""
Google Antigravity Manager - Modelos SQLAlchemy
Modelos de base de datos para gestionar cuentas de Google Antigravity con seguimiento de cuotas.
"""

from datetime import datetime, timedelta, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
import uuid

db = SQLAlchemy()


def generate_uuid():
    """Generar un nuevo UUID como string."""
    return str(uuid.uuid4())


# Modelo de usuario eliminado para modo usuario único
# Usando user_id fijo para compatibilidad
SINGLE_USER_ID = "00000000-0000-0000-0000-000000000000"


class Account(db.Model):
    """Modelo de cuenta de Google Antigravity."""
    
    __tablename__ = 'accounts'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), nullable=False, default=SINGLE_USER_ID)
    email_google = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(100), nullable=True)
    activa = db.Column(db.Boolean, default=False)
    veces_usada = db.Column(db.Integer, default=0)
    tiempo_total_uso = db.Column(db.Interval, default=timedelta(0))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    quotas = db.relationship('Quota', backref='account', lazy='select', cascade='all, delete-orphan')
    sessions = db.relationship('Session', backref='account', lazy='select', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'email_google', name='unique_user_email'),
    )
    
    @classmethod
    def get_all_with_rel(cls, user_id):
        """Obtener todas las cuentas con relaciones cargadas (optimizado)."""
        return cls.query.filter_by(user_id=user_id)\
            .options(joinedload(cls.quotas), joinedload(cls.sessions))\
            .all()
    
    def get_anthropic_quota(self):
        """Obtener cuota de Anthropic para esta cuenta."""
        # Filtrar lista en Python porque lazy='select' devuelve una lista, no una query
        for q in self.quotas:
            if q.provider == 'anthropic':
                return q
        return None
    
    def get_gemini_quota(self):
        """Obtener cuota de Gemini para esta cuenta."""
        for q in self.quotas:
            if q.provider == 'gemini':
                return q
        return None
    
    def is_anthropic_available(self):
        """Verificar si la cuota de Anthropic está disponible."""
        quota = self.get_anthropic_quota()
        if not quota:
            return True
        return quota.is_available()
    
    def is_gemini_available(self):
        """Verificar si la cuota de Gemini está disponible."""
        quota = self.get_gemini_quota()
        if not quota:
            return True
        return quota.is_available()
    
    def get_classification(self):
        """
        Clasificar cuenta según disponibilidad de cuotas.
        
        Retorna:
            'disponible': Ambas cuotas disponibles
            'limite_parcial': Una cuota agotada
            'limite_total': Ambas cuotas agotadas
        """
        anthropic_available = self.is_anthropic_available()
        gemini_available = self.is_gemini_available()
        
        if anthropic_available and gemini_available:
            return 'disponible'
        elif anthropic_available or gemini_available:
            return 'limite_parcial'
        else:
            return 'limite_total'
    
    def to_dict(self, include_quotas=True):
        """Convertir a diccionario para respuesta JSON."""
        data = {
            'id': self.id,
            'email_google': self.email_google,
            'nombre': self.nombre,
            'activa': self.activa,
            'veces_usada': self.veces_usada,
            'tiempo_total_uso': str(self.tiempo_total_uso) if self.tiempo_total_uso else '0:00:00',
            'tiempo_total_segundos': self.tiempo_total_uso.total_seconds() if self.tiempo_total_uso else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'classification': self.get_classification()
        }
        
        if include_quotas:
            data['quotas'] = {
                'anthropic': self.get_anthropic_quota().to_dict() if self.get_anthropic_quota() else {'disponible': True},
                'gemini': self.get_gemini_quota().to_dict() if self.get_gemini_quota() else {'disponible': True}
            }
        
        return data


class Quota(db.Model):
    """Modelo de cuota por proveedor (Anthropic/Gemini)."""
    
    __tablename__ = 'quotas'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(20), default='disponible')
    proximo_reset = db.Column(db.DateTime, nullable=True)
    agotada_en = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'provider', name='unique_account_provider'),
        db.CheckConstraint(provider.in_(['gemini', 'anthropic']), name='valid_provider'),
        db.CheckConstraint(estado.in_(['disponible', 'agotada']), name='valid_estado'),
    )
    
    def is_available(self):
        """Verificar si la cuota está disponible, considerando resets automáticos."""
        if self.estado == 'disponible':
            return True
        
        # Verificar si el reset ya pasó
        if self.proximo_reset:
            # Handle timezone comparison (offset-naive vs offset-aware)
            now = datetime.now(timezone.utc)
            reset_time = self.proximo_reset
            
            # If database time is timezone-aware (Supabase/Postgres), make now aware (UTC)
            if reset_time.tzinfo:
                now = now.replace(tzinfo=timezone.utc)
                
            if now >= reset_time:
                self.reset()
                return True
        
        return False
    
    def mark_exhausted(self, reset_time):
        """Marcar cuota como agotada con tiempo de reinicio."""
        self.estado = 'agotada'
        self.agotada_en = datetime.now(timezone.utc)
        self.proximo_reset = reset_time
        db.session.commit()
    
    def reset(self):
        """Reiniciar cuota a disponible."""
        self.estado = 'disponible'
        self.agotada_en = None
        self.proximo_reset = None
        db.session.commit()
    
    def to_dict(self):
        """Convertir a diccionario para respuesta JSON."""
        return {
            'id': self.id,
            'provider': self.provider,
            'estado': self.estado,
            'disponible': self.is_available(),
            'proximo_reset': self.proximo_reset.isoformat() if self.proximo_reset else None,
            'agotada_en': self.agotada_en.isoformat() if self.agotada_en else None
        }


class Session(db.Model):
    """Modelo de sesión de trabajo."""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)
    inicio = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    fin = db.Column(db.DateTime, nullable=True)
    duracion = db.Column(db.Interval, nullable=True)
    motivo_fin = db.Column(db.String(20), nullable=True)
    
    __table_args__ = (
        db.CheckConstraint(provider.in_(['gemini', 'anthropic']), name='session_valid_provider'),
        db.CheckConstraint(motivo_fin.in_(['cuota_agotada', 'manual', None]), name='valid_motivo'),
    )
    
    def end_session(self, motivo='manual'):
        """
        Finalizar sesión y calcular duración.
        
        Args:
            motivo: 'manual' o 'cuota_agotada'
        """
        # Handle timezone compatibility
        if self.inicio.tzinfo:
            # If inicio is timezone-aware (e.g. from Supabase), make fin aware too
            self.fin = datetime.now(timezone.utc)
        else:
            # If inicio is naive, make fin naive
            self.fin = datetime.now(timezone.utc)
            
        self.duracion = self.fin - self.inicio
        self.motivo_fin = motivo
        
        # Actualizar estadísticas de la cuenta
        account = Account.query.get(self.account_id)
        if account:
            account.activa = False
            
            # Ensure safe increment for veces_usada
            if account.veces_usada is None:
                account.veces_usada = 0
            account.veces_usada += 1
            
            # Ensure safe increment for tiempo_total_uso
            if account.tiempo_total_uso is None:
                from datetime import timedelta
                account.tiempo_total_uso = timedelta(0)
            
            if self.duracion:
                account.tiempo_total_uso += self.duracion
        
        db.session.commit()
    
    def to_dict(self):
        """Convertir a diccionario para respuesta JSON."""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'provider': self.provider,
            'inicio': self.inicio.isoformat() if self.inicio else None,
            'fin': self.fin.isoformat() if self.fin else None,
            'duracion': str(self.duracion) if self.duracion else None,
            'duracion_segundos': self.duracion.total_seconds() if self.duracion else None,
            'motivo_fin': self.motivo_fin,
            'activa': self.fin is None
        }
