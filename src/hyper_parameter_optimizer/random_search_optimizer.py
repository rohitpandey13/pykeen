# -*- coding: utf-8 -*-add # -*- coding: utf-8 -*-
import random
from collections import OrderedDict

import numpy as np

from hyper_parameter_optimizer.abstract_hyper_params_optimizer import AbstractHPOptimizer
from utilities.constants import LEARNING_RATE, MARGIN_LOSS, EMBEDDING_DIM, BATCH_SIZE, NUM_EPOCHS, \
    KG_EMBEDDING_MODEL, NUM_ENTITIES, NUM_RELATIONS, SEED, HYPER_PARAMTER_OPTIMIZATION_PARAMS, NUM_OF_MAX_HPO_ITERS, \
    NORMALIZATION_OF_ENTITIES, EVAL_METRICS, MEAN_RANK, HITS_AT_K, K_FOR_HITS_AT_K, TRANS_E, TRANS_H, TRANS_D, TRANS_R, \
    CONV_E, CONV_E_HEIGHT, CONV_E_WIDTH, CONV_E_INPUT_CHANNELS, CONV_E_OUTPUT_CHANNELS, CONV_E_KERNEL_HEIGHT, \
    CONV_E_KERNEL_WIDTH, CONV_E_INPUT_DROPOUT, CONV_E_OUTPUT_DROPOUT, CONV_E_FEATURE_MAP_DROPOUT
from utilities.evaluation_utils.compute_metrics import compute_mean_rank_and_hits_at_k, compute_mean_rank, \
    compute_hits_at_k
from utilities.initialization_utils.module_initialization_utils import get_kg_embedding_model
from utilities.train_utils import train_model
from utilities.triples_creation_utils.instance_creation_utils import create_mapped_triples


class RandomSearchHPO(AbstractHPOptimizer):

    def _sample_conv_e_specifc_params(self, hyperparams_dict):
        kg_embedding_model_config = OrderedDict()
        kg_embedding_model_config[CONV_E_HEIGHT] = random.choice(hyperparams_dict[CONV_E_HEIGHT])
        kg_embedding_model_config[CONV_E_WIDTH] = random.choice(hyperparams_dict[CONV_E_WIDTH])
        kg_embedding_model_config[CONV_E_INPUT_CHANNELS] = random.choice(hyperparams_dict[CONV_E_INPUT_CHANNELS])
        kg_embedding_model_config[CONV_E_OUTPUT_CHANNELS] = random.choice(hyperparams_dict[CONV_E_OUTPUT_CHANNELS])
        kg_embedding_model_config[CONV_E_KERNEL_HEIGHT] = random.choice(hyperparams_dict[CONV_E_KERNEL_HEIGHT])
        kg_embedding_model_config[CONV_E_KERNEL_WIDTH] = random.choice(hyperparams_dict[CONV_E_KERNEL_WIDTH])
        kg_embedding_model_config[CONV_E_INPUT_DROPOUT] = random.choice(hyperparams_dict[CONV_E_INPUT_DROPOUT])
        kg_embedding_model_config[CONV_E_OUTPUT_DROPOUT] = random.choice(hyperparams_dict[CONV_E_OUTPUT_DROPOUT])
        kg_embedding_model_config[CONV_E_FEATURE_MAP_DROPOUT] = random.choice(hyperparams_dict[CONV_E_FEATURE_MAP_DROPOUT])

        return kg_embedding_model_config

    def _sample_trans_x_specifc_params(self, hyperparams_dict):
        kg_embedding_model_config = OrderedDict()
        kg_embedding_model_config[MARGIN_LOSS] = random.choice(hyperparams_dict[MARGIN_LOSS])
        kg_embedding_model_config[MARGIN_LOSS] = random.choice(hyperparams_dict[MARGIN_LOSS])
        kg_embedding_model_config[NORMALIZATION_OF_ENTITIES] = hyperparams_dict[NORMALIZATION_OF_ENTITIES]

        return kg_embedding_model_config

    def optimize_hyperparams(self, train_pos, test_pos, entity_to_id, rel_to_id, mapped_pos_train_tripels, config,
                             device, seed):
        np.random.seed(seed=seed)

        trained_models = []
        eval_results = []
        entity_to_ids = []
        rel_to_ids = []
        models_params = []
        eval_summaries = []
        epoch_losses = []

        # general params
        hyperparams_dict = config[HYPER_PARAMTER_OPTIMIZATION_PARAMS]
        num_epochs = hyperparams_dict[NUM_EPOCHS]
        embedding_dims = hyperparams_dict[EMBEDDING_DIM]
        learning_rates = hyperparams_dict[LEARNING_RATE]
        batch_sizes = hyperparams_dict[BATCH_SIZE]
        max_iters = hyperparams_dict[NUM_OF_MAX_HPO_ITERS]
        embedding_model = hyperparams_dict[KG_EMBEDDING_MODEL]

        # Configuration
        kg_embedding_model_config = OrderedDict()
        kg_embedding_model_config[KG_EMBEDDING_MODEL] = embedding_model

        eval_metrics = config[EVAL_METRICS]
        is_mean_rank_selected = True if 'mean_rank' in eval_metrics else False
        is_hits_at_k_selected = True if 'hits_at_k' in eval_metrics else False

        eval_summary = OrderedDict()

        all_entities = np.array(list(entity_to_id.values()))

        if embedding_model in [TRANS_E, TRANS_H, TRANS_D, TRANS_R]:
            # Sample TransX (where X is element of {E,H,R,D})
            param_sampling_fct = self._sample_trans_x_specifc_params

        if embedding_model == CONV_E:
            param_sampling_fct = self._sample_conv_e_specifc_params

        for _ in range(max_iters):

            # Sample general hyper-params
            kg_embedding_model_config[LEARNING_RATE] = random.choice(learning_rates)
            kg_embedding_model_config[EMBEDDING_DIM] = random.choice(embedding_dims)
            kg_embedding_model_config[NUM_EPOCHS] = random.choice(num_epochs)
            kg_embedding_model_config[BATCH_SIZE] = random.choice(batch_sizes)
            kg_embedding_model_config[NUM_ENTITIES] = len(entity_to_id)
            kg_embedding_model_config[NUM_RELATIONS] = len(rel_to_id)
            kg_embedding_model_config[SEED] = seed

            # Sample model specific hyper-params
            kg_embedding_model_config.update(param_sampling_fct(hyperparams_dict))

            # Configure defined model
            kg_embedding_model = get_kg_embedding_model(config=kg_embedding_model_config)

            models_params.append(kg_embedding_model_config)
            entity_to_ids.append(entity_to_id)
            rel_to_ids.append(rel_to_id)

            trained_model, epoch_loss = train_model(kg_embedding_model=kg_embedding_model,
                                        learning_rate=kg_embedding_model_config[LEARNING_RATE],
                                        num_epochs=kg_embedding_model_config[NUM_EPOCHS],
                                        batch_size=kg_embedding_model_config[BATCH_SIZE],
                                        pos_triples=mapped_pos_train_tripels,
                                        device=device, seed=seed)

            # Evaluate trained model
            mapped_pos_test_tripels, _, _ = create_mapped_triples(test_pos, entity_to_id=entity_to_id,
                                                                  rel_to_id=rel_to_id)

            if is_mean_rank_selected and is_hits_at_k_selected:
                k = config[K_FOR_HITS_AT_K]
                mean_rank, hits_at_k = compute_mean_rank_and_hits_at_k(all_entities=all_entities,
                                                                       kg_embedding_model=trained_model,
                                                                       triples=mapped_pos_test_tripels,
                                                                       device=device, k=k)
                eval_summary[MEAN_RANK] = mean_rank
                eval_summary[HITS_AT_K] = hits_at_k
                eval_results.append(mean_rank)
                eval_summaries.append(eval_summary)

            if is_mean_rank_selected == True and is_hits_at_k_selected == False:
                mean_rank = compute_mean_rank(all_entities=all_entities, kg_embedding_model=trained_model,
                                              triples=mapped_pos_test_tripels, device=device)
                eval_summary[MEAN_RANK] = mean_rank
                eval_results.append(mean_rank)
                eval_summaries.append(eval_summary)
            if is_hits_at_k_selected == True and is_mean_rank_selected == False:
                k = config[K_FOR_HITS_AT_K]
                hits_at_k = compute_hits_at_k(all_entities=all_entities, kg_embedding_model=trained_model,
                                              triples=mapped_pos_test_tripels, device=device, k=k)
                eval_summary[HITS_AT_K] = hits_at_k
                eval_results.append(hits_at_k)
                eval_summaries.append(eval_summary)

            trained_models.append(trained_model)
            epoch_losses.append(epoch_loss)

        index_of_max = np.argmax(a=eval_results)




        return trained_models[index_of_max],epoch_losses[index_of_max], entity_to_ids[index_of_max], rel_to_ids[index_of_max], \
               eval_summaries[index_of_max], MEAN_RANK, models_params[index_of_max]