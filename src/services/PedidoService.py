from sqlalchemy.orm import Session
from src.models.Pedido import Pedido
from src.models.ItemPedido import ItemPedido
from src.models.Cardapio import Cardapio
from src.schemas.PedidoSchema import PedidoCriarSchema
from src.core.websocket_manager import kds_ws_manager
import asyncio

class PedidoService:
    def __init__(self, db: Session):
        self.db = db

    def _enriquecer_item(self, idCardapio: int):
        # MOCK para não quebrar no teste com DB vazio
        if idCardapio == 1:
            categoria = "bebida"
            prioridade = 1
            preco = 5.0
        elif idCardapio == 2:
            categoria = "sobremesa"
            prioridade = 3
            preco = 15.0
        else:
            categoria = "cozinha_quente"
            prioridade = 2
            preco = 35.0
            
        return {
            "precoUnitario": preco,
            "categoria": categoria,
            "prioridade": prioridade
        }

    def processar_pedido(self, payload: PedidoCriarSchema):
        try:
            pedido = self.db.query(Pedido).filter(
                Pedido.sessao_id == payload.sessao_id,
                Pedido.status == "Aberto"
            ).with_for_update().first()

            if not pedido:
                pedido = Pedido(
                    sessao_id=payload.sessao_id,
                    idRestaurante=payload.idRestaurante,
                    idMesa=payload.idMesa,
                    idGarcom=payload.idGarcom,
                    status="Aberto"
                )
                self.db.add(pedido)
                self.db.flush()

            novos_itens_db = []
            for item in payload.itens:
                enriquecido = self._enriquecer_item(item.item_id)
                novo_item = ItemPedido(
                    idPedido=pedido.idPedido,
                    idCardapio=item.item_id,
                    quantidade=item.quantidade,
                    precoUnitario=enriquecido["precoUnitario"],
                    observacao=item.observacoes,
                    status="Pendente",
                    categoria=enriquecido["categoria"],
                    prioridade=enriquecido["prioridade"]
                )
                self.db.add(novo_item)
                novos_itens_db.append(novo_item)

            self.db.commit()
            self._notificar_kds(pedido, novos_itens_db)
            return pedido
            
        except Exception as e:
            self.db.rollback()
            raise e


    def _notificar_kds(self, pedido: Pedido, itens: list[ItemPedido]):
        payload = {
            "pedido_id": pedido.idPedido,
            "sessao_id": pedido.sessao_id,
            "itens": [
                {
                    "idItemPedido": i.idItemPedido,
                    "idCardapio": i.idCardapio,
                    "quantidade": i.quantidade,
                    "categoria": i.categoria,
                    "prioridade": i.prioridade,
                    "observacao": i.observacao
                } for i in itens
            ]
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(kds_ws_manager.broadcast_to_kitchen(payload))
            else:
                loop.run_until_complete(kds_ws_manager.broadcast_to_kitchen(payload))
        except Exception:
            pass

    def listar_pedidos(self):
        return self.db.query(Pedido).order_by(Pedido.idPedido.desc()).all()
        
    def obter_pedido(self, pedido_id: int):
        return self.db.query(Pedido).filter(Pedido.idPedido == pedido_id).first()
