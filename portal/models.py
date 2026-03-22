"""
Modelos da aplicação de portal (portal).

Define as estruturas de dados principais para gerenciar solicitações,
status e dispositivos no sistema FRNR.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class SolicitacaoStatus(models.TextChoices):
    """
    Enumeração de possíveis status de uma solicitação.
    
    Fluxo geral: RASCUNHO -> EM_FILA -> EM_PROJETO -> AGUARDANDO_APROVACAO 
                -> APROVADO -> CONCLUIDO ou REPROVADO
    """
    RASCUNHO = "RASCUNHO", "Rascunho"
    EM_FILA = "EM_FILA", "Em fila"
    EM_PROJETO = "EM_PROJETO", "Em projeto"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
    RETRABALHO = "RETRABALHO", "Retrabalho"
    APROVADO = "APROVADO", "Aprovado"
    REPROVADO = "REPROVADO", "Reprovado"
    CONCLUIDO = "CONCLUIDO", "Concluído"
    CANCELADO = "CANCELADO", "Cancelado"


class Prioridade(models.IntegerChoices):
    """
    Enumeração de níveis de prioridade para solicitações.
    
    Quanto maior o valor, maior a prioridade:
    1 = Baixa, 2 = Média, 3 = Alta, 4 = Crítica
    """
    BAIXA = 1, "Baixa"
    MEDIA = 2, "Média"
    ALTA = 3, "Alta"
    CRITICA = 4, "Crítica"


class Solicitacao(models.Model):
    """
    Modelo principal para armazenar solicitações de dispositivos.
    
    Representa uma requisição de um dispositivo que deve passar por um fluxo
    de aprovação, projeto e fabricação. Armazena informações técnicas,
    status de progresso e metadados do SAP.
    
    Atributos de Descrição:
        titulo: Título da solicitação
        descricao: Descrição detalhada
        secao: Seção responsável
        job: Job do projeto SAP
        
    Atributos Técnicos:
        sufixo: Sufixo do dispositivo
        numero_dispositivo: Número único do dispositivo
        numero_moc: Número do MOC (Manufacturing Order Card)
        desenho_referencia: Desenho de referência
        wc: Work Center (Centro de trabalho)
        
    Atributos de Processo:
        status: Status atual da solicitação (EM_FILA, EM_PROJETO, etc)
        prioridade: Nível de prioridade (1-4)
        criado_por: Usuário que criou a solicitação (Solicitante)
        atribuido_para: Projetista responsável (pode estar nulo)
        
    Atributos de Timeline:
        solicitado_em: Data/hora do pedido
        criado_em: Data/hora de criação no sistema
        atualizado_em: Data/hora da última atualização
        prazo_estimado: Prazo para conclusão
        baseline_ame: Data baseline AME
        baseline_producao: Data baseline produção
    """
    
    # Campos de Identificação e Descrição
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    secao = models.CharField(max_length=120, blank=True)
    job = models.CharField(max_length=120, blank=True)
    jobs_envolvidas = models.CharField(max_length=200, blank=True)
    
    # Campos Técnicos do Dispositivo
    sufixo = models.CharField(max_length=80, blank=True)
    descricao_ferramenta = models.TextField(blank=True)
    desenho_referencia = models.TextField(blank=True)
    wc = models.CharField(max_length=80, blank=True)
    quantidade = models.PositiveIntegerField(default=1)
    
    # Campos SAP e Identificadores
    solicitado_em = models.DateTimeField(blank=True, null=True)
    evento_sap = models.CharField(max_length=120, blank=True)
    numero_moc = models.CharField(max_length=80, blank=True)
    numero_dispositivo = models.CharField(max_length=80, blank=True)
    
    # Campos de Contexto e Classificação
    area = models.CharField(max_length=120, blank=True)
    tipo_identificacao = models.CharField(max_length=80, blank=True)
    linha_produto = models.CharField(max_length=80, blank=True)
    
    # Campos Técnicos Adicionais
    descricao_tecnica = models.TextField(blank=True)
    material = models.CharField(max_length=120, blank=True)
    tratamento = models.CharField(max_length=120, blank=True)
    dim_criticas = models.TextField(blank=True)
    
    # Campos de Aprovação e Observações
    observacoes_projeto = models.TextField(blank=True)
    observacoes_aprovacao = models.TextField(blank=True)
    anexos = models.FileField(upload_to="solicitacoes/anexos/", blank=True, null=True)
    
    # Campos de Timeline
    prazo_estimado = models.DateField(blank=True, null=True)
    baseline_ame = models.DateField(blank=True, null=True)
    baseline_producao = models.DateField(blank=True, null=True)

    # Campos de Workflow (aprovacao, retrabalho, cancelamento e conclusao)
    aprovado_em = models.DateTimeField(blank=True, null=True)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_aprovadas",
    )
    aprovado_comentario = models.TextField(blank=True)

    reprovado_em = models.DateTimeField(blank=True, null=True)
    reprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_reprovadas",
    )
    reprovado_comentario = models.TextField(blank=True)

    retrabalho_em = models.DateTimeField(blank=True, null=True)
    retrabalho_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_retrabalho",
    )
    retrabalho_comentario = models.TextField(blank=True)

    cancelado_em = models.DateTimeField(blank=True, null=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_canceladas",
    )
    cancelado_comentario = models.TextField(blank=True)

    concluido_em = models.DateTimeField(blank=True, null=True)
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_concluidas",
    )
    concluido_comentario = models.TextField(blank=True)

    # Campos de Status e Controle
    status = models.CharField(
        max_length=30,
        choices=SolicitacaoStatus.choices,
        default=SolicitacaoStatus.EM_FILA,
        db_index=True,  # Indexado para melhor performance em filtros
    )
    prioridade = models.IntegerField(
        choices=Prioridade.choices, 
        default=Prioridade.MEDIA
    )

    # Relacionamentos com Usuários
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitacoes_criadas",  # Acesso: user.solicitacoes_criadas.all()
    )

    atribuido_para = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_atribuidas",  # Acesso: user.solicitacoes_atribuidas.all()
    )

    # Campos de Auditoria
    criado_em = models.DateTimeField(default=timezone.now, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        # Ordena por data de criação descendente (mais recentes primeiro)
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        """Representação em string da solicitação."""
        return f"#{self.id} - {self.titulo}"

    def mudar_status(self, novo_status: str, usuario, comentario: str = ""):
        """
        Altera o status da solicitação e registra a mudança no histórico.
        
        Args:
            novo_status: Novo status (deve estar em SolicitacaoStatus.choices)
            usuario: Usuário que fez a alteração
            comentario: Comentário opcional sobre a mudança
            
        Comportamento:
            - Se o status for igual ao novo status, não faz nada
            - Salva o novo status no banco de dados
            - Cria um registro de log da mudança
        """
        status_antigo = self.status
        if status_antigo == novo_status:
            return  # Evita registrar mudança desnecessária

        # Atualiza o status e guarda a data de atualização
        self.status = novo_status
        update_fields = {"status", "atualizado_em"}
        agora = timezone.now()
        if novo_status == SolicitacaoStatus.APROVADO:
            self.aprovado_em = agora
            self.aprovado_por = usuario
            self.aprovado_comentario = comentario or ""
            update_fields.update(
                {"aprovado_em", "aprovado_por", "aprovado_comentario"}
            )
        elif novo_status == SolicitacaoStatus.REPROVADO:
            self.reprovado_em = agora
            self.reprovado_por = usuario
            self.reprovado_comentario = comentario or ""
            update_fields.update(
                {"reprovado_em", "reprovado_por", "reprovado_comentario"}
            )
        elif novo_status == SolicitacaoStatus.RETRABALHO:
            self.retrabalho_em = agora
            self.retrabalho_por = usuario
            self.retrabalho_comentario = comentario or ""
            update_fields.update(
                {"retrabalho_em", "retrabalho_por", "retrabalho_comentario"}
            )
        elif novo_status == SolicitacaoStatus.CANCELADO:
            self.cancelado_em = agora
            self.cancelado_por = usuario
            self.cancelado_comentario = comentario or ""
            update_fields.update(
                {"cancelado_em", "cancelado_por", "cancelado_comentario"}
            )
        elif novo_status == SolicitacaoStatus.CONCLUIDO:
            self.concluido_em = agora
            self.concluido_por = usuario
            self.concluido_comentario = comentario or ""
            update_fields.update(
                {"concluido_em", "concluido_por", "concluido_comentario"}
            )
        self.save(update_fields=list(update_fields))

        # Registra a mudança de status no histórico
        SolicitacaoLog.objects.create(
            solicitacao=self,
            alterado_por=usuario,
            status_de=status_antigo,
            status_para=novo_status,
            comentario=comentario,
        )


class SolicitacaoLog(models.Model):
    """
    Modelo para registrar histórico de mudanças de status de solicitações.
    
    Cada vez que uma solicitação muda de status, um novo registro é criado
    nesta tabela para auditoria e rastreamento.
    
    Atributos:
        solicitacao: Referência à solicitação que foi modificada
        alterado_por: Usuário que fez a alteração
        status_de: Status anterior
        status_para: Novo status
        comentario: Observação sobre a mudança
        criado_em: Data/hora da mudança
    """
    
    solicitacao = models.ForeignKey(
        Solicitacao, 
        on_delete=models.CASCADE, 
        related_name="logs"  # Acesso: solicitacao.logs.all()
    )
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT
    )

    # Rastreamento de mudança de status
    status_de = models.CharField(max_length=30, choices=SolicitacaoStatus.choices)
    status_para = models.CharField(max_length=30, choices=SolicitacaoStatus.choices)

    # Informações adicionais
    comentario = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        # Ordena por data descendente (mais recentes primeiro)
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        """Representação em string do log."""
        return f"Solicitação #{self.solicitacao_id}: {self.status_de} -> {self.status_para}"


class DispositivoCatalogo(models.Model):
    """
    Modelo para armazenar o catálogo de dispositivos disponíveis.
    
    Permite que projetistas e solicitantes selecionem dispositivos pré-existentes
    de um catálogo em vez de criar novos.
    
    Atributos:
        codigo: Código único do dispositivo (ex: "0321", "0359")
        descricao: Descrição detalhada do dispositivo
    """
    
    codigo = models.CharField(
        max_length=40, 
        unique=True  # Garante que cada código é único
    )
    descricao = models.TextField()

    class Meta:
        # Ordena pelo código em ordem alfabética/numérica
        ordering = ["codigo"]

    def __str__(self) -> str:
        """Representação em string do dispositivo."""
        return f"{self.codigo} - {self.descricao}"


class AuditLog(models.Model):
    """
    Modelo para registrar ações gerais de auditoria no sistema.

    Armazena ações de solicitantes, projetistas e dispositivos com
    metadados básicos para rastreabilidade.
    """

    acao = models.CharField(max_length=80, db_index=True)
    descricao = models.TextField(blank=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    grupo = models.CharField(max_length=40, blank=True)

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    entidade = models.CharField(max_length=80, blank=True)
    entidade_id = models.PositiveIntegerField(null=True, blank=True)

    dados = models.JSONField(blank=True, null=True)

    ip = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)
    path = models.CharField(max_length=200, blank=True)
    method = models.CharField(max_length=10, blank=True)

    criado_em = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        usuario = getattr(self.usuario, "username", "usuario")
        return f"{self.acao} por {usuario} em {self.criado_em:%d/%m/%Y %H:%M}"

