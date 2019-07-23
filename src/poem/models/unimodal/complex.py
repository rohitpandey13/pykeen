# -*- coding: utf-8 -*-

"""Implementation of the Complex model based on the open world assumption (OWA)."""

from typing import Optional

import torch
import torch.nn as nn
from torch.nn.init import xavier_normal_

from poem.customized_loss_functions.softplus_loss import SoftplusLoss
from poem.instance_creation_factories.triples_factory import TriplesFactory
from poem.utils import slice_triples
from ..base import BaseModule
from ...typing import OptionalLoss


# TODO: Combine with the ComplexCWA Module
class ComplEx(BaseModule):
    """An implementation of ComplEx [trouillon2016]_."""

    def __init__(
            self,
            triples_factory: TriplesFactory,
            entity_embeddings_real: Optional[nn.Embedding] = None,
            entity_embeddings_img: Optional[nn.Embedding] = None,
            relation_embeddings_real: Optional[nn.Embedding] = None,
            relation_embeddings_img: Optional[nn.Embedding] = None,
            embedding_dim: int = 200,
            neg_label: float = -1.,
            regularization_factor: float = 0.01,
            criterion: OptionalLoss = None,
            preferred_device: Optional[str] = None,
            random_seed: Optional[int] = None,
    ):
        if criterion is None:
            criterion = SoftplusLoss(reduction='mean')

        super().__init__(
            triples_factory=triples_factory,
            embedding_dim=embedding_dim,
            criterion=criterion,
            preferred_device=preferred_device,
            random_seed=random_seed,
        )

        self.neg_label = neg_label
        self.regularization_factor = torch.nn.Parameter(torch.Tensor([regularization_factor]))
        self.current_regularization_term = None
        self.criterion = criterion

        # The embeddings are first initialized when calling the get_grad_params function
        self.entity_embeddings_real = entity_embeddings_real
        self.entity_embeddings_img = entity_embeddings_img
        self.relation_embeddings_real = relation_embeddings_real
        self.relation_embeddings_img = relation_embeddings_img

        if None in [
            self.entity_embeddings_real,
            self.entity_embeddings_img,
            self.relation_embeddings_real,
            self.relation_embeddings_img,
        ]:
            self._init_embeddings()

    def _init_embeddings(self):
        self.entity_embeddings_real = nn.Embedding(self.num_entities, self.embedding_dim)
        self.entity_embeddings_img = nn.Embedding(self.num_entities, self.embedding_dim)
        self.relation_embeddings_real = nn.Embedding(self.num_relations, self.embedding_dim)
        self.relation_embeddings_img = nn.Embedding(self.num_relations, self.embedding_dim)
        xavier_normal_(self.entity_embeddings_real.weight.data)
        xavier_normal_(self.entity_embeddings_img.weight.data)
        xavier_normal_(self.relation_embeddings_real.weight.data)
        xavier_normal_(self.relation_embeddings_img.weight.data)

    def forward_owa(self, triples):
        heads_real, relations_real, tails_real, heads_img, relations_img, tails_img = \
            self._get_triple_embeddings(triples)
        # ComplEx space bilinear product (equivalent to HolE)
        # *: Elementwise multiplication
        real_real_real = heads_real * relations_real * tails_real
        real_img_img = heads_real * relations_img * tails_img
        img_real_img = heads_img * relations_real * tails_img
        img_img_real = heads_img * relations_img * tails_real
        scores = torch.sum(real_real_real + real_img_img + img_real_img - img_img_real, dim=1)
        self.current_regularization_term = self._compute_regularization_term(
            heads_real, relations_real, tails_real,
            heads_img, relations_img, tails_img,
        )
        return scores

    # TODO: Implement forward_cwa

    def _compute_regularization_term(
            self,
            heads_real,
            relations_real,
            tails_real,
            heads_img,
            relations_img,
            tails_img,
    ):
        regularization_term = torch.mean(heads_real ** 2)
        regularization_term += torch.mean(heads_img ** 2)
        regularization_term += torch.mean(relations_real ** 2)
        regularization_term += torch.mean(relations_img ** 2)
        regularization_term += torch.mean(tails_real ** 2)
        regularization_term += torch.mean(tails_img ** 2)
        return regularization_term

    def compute_label_loss(self, predictions: torch.Tensor, labels: torch.Tensor):
        loss = super()._compute_label_loss(predictions=predictions, labels=labels)
        loss += self.regularization_factor.item() * self.current_regularization_term
        return loss

    def _get_triple_embeddings(self, triples):
        heads, relations, tails = slice_triples(triples)
        return (
            self._get_embeddings(
                elements=heads,
                embedding_module=self.entity_embeddings_real,
                embedding_dim=self.embedding_dim,
            ),
            self._get_embeddings(
                elements=relations,
                embedding_module=self.relation_embeddings_real,
                embedding_dim=self.embedding_dim,
            ),
            self._get_embeddings(
                elements=tails,
                embedding_module=self.entity_embeddings_real,
                embedding_dim=self.embedding_dim,
            ),
            self._get_embeddings(
                elements=heads,
                embedding_module=self.entity_embeddings_img,
                embedding_dim=self.embedding_dim,
            ),
            self._get_embeddings(
                elements=relations,
                embedding_module=self.relation_embeddings_img,
                embedding_dim=self.embedding_dim,
            ),
            self._get_embeddings(
                elements=tails,
                embedding_module=self.entity_embeddings_img,
                embedding_dim=self.embedding_dim,
            ),
        )