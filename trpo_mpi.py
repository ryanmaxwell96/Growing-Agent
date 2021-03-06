from baselines.common import explained_variance, zipsame, dataset
from baselines import logger
import baselines.common.tf_util as U
import tensorflow as tf, numpy as np
import time
import os.path as osp
import os
from baselines.common import colorize
from collections import deque
from baselines.common import set_global_seeds
from baselines.common.models import get_network_builder
from baselines.common.mpi_adam import MpiAdam
from baselines.common.cg import cg
from baselines.common.policies import PolicyWithValue
from baselines.common.vec_env.vec_env import VecEnv
from contextlib import contextmanager

try:
    from mpi4py import MPI
except ImportError:
    MPI = None

from baselines.common.vec_env.vec_video_recorder import VecVideoRecorder

import math
video_recording_test = 1

'''
python3 -m baselines.run --alg=trpo_mpi --env=Ant-v2 --num_timesteps=5e5 --log_path=~/Documents/MyAntFile --load_path=~/Documents/7_MyAntFile_Back_Legs_Fixed/First_Half/ --save_path=~/Documents/MyAntFile
'''

def traj_segment_generator(pi, env, horizon):
    # Initialize state variables
    t = 0
    ac = env.action_space.sample()
    new = True
    rew = 0.0
    ob = env.reset() # in vec_normalize.py
    if not isinstance(env, VecEnv):
      ob = np.expand_dims(ob, axis=0)

    # ------------------- NEW ----------------------
    ep_rets_for = []
    ep_rets_ctrl = []
    ep_rets_con = []
    ep_rets_sur = []
    # ----------------------------------------------

    cur_ep_ret = 0
    cur_ep_len = 0
    ep_rets = []
    ep_lens = []

    # Initialize history arrays
    obs = np.array([ob for _ in range(horizon)])
    rews = np.zeros(horizon, 'float32')
    vpreds = np.zeros(horizon, 'float32')
    news = np.zeros(horizon, 'int32')
    acs = np.array([ac for _ in range(horizon)])
    prevacs = acs.copy()
    while True:
        prevac = ac
        ob = tf.constant(ob)
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # ---------------- PHASE 1 -------------------------------------------#
        # pi.kill_actions() 
        # ---------------- PHASE 2 -------------------------------------------#
        # pi.hold_weights()
        # --------------------------------------------------------------------#
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        ac, vpred, _, _ = pi.step(ob)
        # print('weight,bias')
        # print(weight)
        # print(bias)
        # print('ac')
        # print(ac)
        # input('')
        ac = ac.numpy()

        # Slight weirdness here because we need value function at time T
        # before returning segment [0, T-1] so we get the correct
        # terminal value
        if t > 0 and t % horizon == 0:
            yield {"ob" : obs, "rew" : rews, "vpred" : vpreds, "new" : news,
                    "ac" : acs, "prevac" : prevacs, "nextvpred": vpred * (1 - new),
                    "ep_rets" : ep_rets, "ep_lens" : ep_lens, "ep_rets_for" : ep_rets_for,
                    "ep_rets_ctrl" : ep_rets_ctrl, "ep_rets_con" : ep_rets_con, "ep_rets_sur" : ep_rets_sur}

            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # ---------------- PHASE 1 -------------------------------------------#
            # pi.kill_actions()
            # ---------------- PHASE 2 -------------------------------------------#
            # pi.hold_weights()
            # --------------------------------------------------------------------#
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

            # ------------------- NEW ----------------------
            ep_rets_for = []
            ep_rets_ctrl = []
            ep_rets_con = []
            ep_rets_sur = []
            # ----------------------------------------------

            # print('weight,bias')
            # print(weight)
            # print(bias)
            _, vpred, _, _ = pi.step(ob)
            # Be careful!!! if you change the downstream algorithm to aggregate
            # several of these batches, then be sure to do a deepcopy
            ep_rets = []
            ep_lens = []
        i = t % horizon
        obs[i] = ob
        vpreds[i] = vpred.numpy()
        news[i] = new
        acs[i] = ac
        prevacs[i] = prevac

        ######################################################################################################################
        ## front pointed right (x)
        # ac[0][0] = 0.2 # front_right hip
        # ac[0][1] = 0.2 # front_right ankle
        # ac[0][2] = 0.2 # front_left hip
        # ac[0][3] = 0.2 # front_left ankle

        # # Uncomment These for First Half of Training
        # ac[0][4] = 0.2 # back_left hip
        # ac[0][5] = 0.2 # back_left ankle
        # ac[0][6] = -0.2 # back_right hip
        # ac[0][7] = 0.2 # back_right ankle
        ######################################################################################################################

        ob, rew, new, info = env.step(ac)
        # print('env',env)
        # print('rew trpo_mpi',rew)
        # print('info',info)
        # print('info sum',info[0]['reward_forward']+info[0]['reward_ctrl']+info[0]['reward_contact']+info[0]['reward_survive'])
        # input('')

        if not isinstance(env, VecEnv):
          ob = np.expand_dims(ob, axis=0)
        rews[i] = rew

        cur_ep_ret += rew
        cur_ep_len += 1
        if new:

            # ------------------- NEW ----------------------
            ep_rets_for.append(info[0]['reward_forward'])
            ep_rets_ctrl.append(info[0]['reward_ctrl'])
            ep_rets_con.append(info[0]['reward_contact'])
            ep_rets_sur.append(info[0]['reward_survive'])
            # ----------------------------------------------

            ep_rets.append(cur_ep_ret)
            ep_lens.append(cur_ep_len)
            cur_ep_ret = 0
            cur_ep_len = 0
            ob = env.reset()
            if not isinstance(env, VecEnv):
              ob = np.expand_dims(ob, axis=0)
        t += 1

def add_vtarg_and_adv(seg, gamma, lam):
    new = np.append(seg["new"], 0) # last element is only used for last vtarg, but we already zeroed it if last new = 1
    vpred = np.append(seg["vpred"], seg["nextvpred"])
    T = len(seg["rew"])
    seg["adv"] = gaelam = np.empty(T, 'float32')
    rew = seg["rew"]
    lastgaelam = 0
    for t in reversed(range(T)):
        nonterminal = 1-new[t+1]
        delta = rew[t] + gamma * vpred[t+1] * nonterminal - vpred[t]
        gaelam[t] = lastgaelam = delta + gamma * lam * nonterminal * lastgaelam
    seg["tdlamret"] = seg["adv"] + seg["vpred"]

def learn(*,
        network,
        env,
        save,
        total_timesteps,
        timesteps_per_batch=1024, # what to train on
        max_kl=0.001,
        cg_iters=10,
        gamma=0.99,
        lam=1.0, # advantage estimation
        seed=None,
        ent_coef=0.0,
        cg_damping=1e-2,
        vf_stepsize=3e-4,
        vf_iters =3,
        max_episodes=0, max_iters=0,  # ttotal_timestepsime constraint
        callback=None,
        load_path=None,
        **network_kwargs
        ):
    '''
    learn a policy function with TRPO algorithm

    Parameters:
    ----------

    network                 neural network to learn. Can be either string ('mlp', 'cnn', 'lstm', 'lnlstm' for basic types)
                            or function that takes input placeholder and returns tuple (output, None) for feedforward nets
                            or (output, (state_placeholder, state_output, mask_placeholder)) for recurrent nets

    env                     environment (one of the gym environments or wrapped via baselines.common.vec_env.VecEnv-type class

    timesteps_per_batch     timesteps per gradient estimation batch

    max_kl                  max KL divergence between old policy and new policy ( KL(pi_old || pi) )

    ent_coef                coefficient of policy entropy term in the optimization objective

    cg_iters                number of iterations of conjugate gradient algorithm

    cg_damping              conjugate gradient damping

    vf_stepsize             learning rate for adam optimizer used to optimie value function loss

    vf_iters                number of iterations of value function optimization iterations per each policy optimization step

    total_timesteps           max number of timesteps

    max_episodes            max number of episodes

    max_iters               maximum number of policy optimization iterations

    callback                function to be called with (locals(), globals()) each policy optimization step

    load_path               str, path to load the model from (default: None, i.e. no model is loaded)

    **network_kwargs        keyword arguments to the policy / network builder. See baselines.common/policies.py/build_policy and arguments to a particular type of network

    Returns:
    -------

    learnt model

    '''

    if MPI is not None:
        nworkers = MPI.COMM_WORLD.Get_size()
        rank = MPI.COMM_WORLD.Get_rank()
    else:
        nworkers = 1
        rank = 0

    set_global_seeds(seed)

    np.set_printoptions(precision=3)
    # Setup losses and stuff
    # ----------------------------------------
    ob_space = env.observation_space
    ac_space = env.action_space

    if isinstance(network, str):
        network,network_model = get_network_builder(network)(**network_kwargs)

    with tf.name_scope("pi"):
        pi_policy_network = network(ob_space.shape)
        pi_value_network = network(ob_space.shape)
        pi = PolicyWithValue(ac_space, pi_policy_network, pi_value_network)
    with tf.name_scope("oldpi"):
        old_pi_policy_network = network(ob_space.shape)
        old_pi_value_network = network(ob_space.shape)
        oldpi = PolicyWithValue(ac_space, old_pi_policy_network, old_pi_value_network)

    pi_var_list = pi_policy_network.trainable_variables + list(pi.pdtype.trainable_variables)
    old_pi_var_list = old_pi_policy_network.trainable_variables + list(oldpi.pdtype.trainable_variables)
    vf_var_list = pi_value_network.trainable_variables + pi.value_fc.trainable_variables
    old_vf_var_list = old_pi_value_network.trainable_variables + oldpi.value_fc.trainable_variables

    if load_path is not None:
        load_path = osp.expanduser(load_path)
        ckpt = tf.train.Checkpoint(model=pi)
        manager = tf.train.CheckpointManager(ckpt, load_path, max_to_keep=None)
        ckpt.restore(manager.latest_checkpoint)

    vfadam = MpiAdam(vf_var_list)

    get_flat = U.GetFlat(pi_var_list)
    set_from_flat = U.SetFromFlat(pi_var_list)
    loss_names = ["optimgain", "meankl", "entloss", "surrgain", "entropy"]
    shapes = [var.get_shape().as_list() for var in pi_var_list]


    def assign_old_eq_new():
        for pi_var, old_pi_var in zip(pi_var_list, old_pi_var_list):
            old_pi_var.assign(pi_var)
        for vf_var, old_vf_var in zip(vf_var_list, old_vf_var_list):
            old_vf_var.assign(vf_var)

    @tf.function
    def compute_lossandgrad(ob, ac, atarg):
        with tf.GradientTape() as tape:
            old_policy_latent = oldpi.policy_network(ob)
            old_pd, _ = oldpi.pdtype.pdfromlatent(old_policy_latent)
            policy_latent = pi.policy_network(ob)
            pd, _ = pi.pdtype.pdfromlatent(policy_latent)
            kloldnew = old_pd.kl(pd)
            ent = pd.entropy()
            meankl = tf.reduce_mean(kloldnew)
            meanent = tf.reduce_mean(ent)
            entbonus = ent_coef * meanent
            ratio = tf.exp(pd.logp(ac) - old_pd.logp(ac))
            surrgain = tf.reduce_mean(ratio * atarg)
            optimgain = surrgain + entbonus
            losses = [optimgain, meankl, entbonus, surrgain, meanent]
        gradients = tape.gradient(optimgain, pi_var_list)
        return losses + [U.flatgrad(gradients, pi_var_list)]

    @tf.function
    def compute_losses(ob, ac, atarg):
        old_policy_latent = oldpi.policy_network(ob)
        old_pd, _ = oldpi.pdtype.pdfromlatent(old_policy_latent)
        policy_latent = pi.policy_network(ob)
        pd, _ = pi.pdtype.pdfromlatent(policy_latent)
        kloldnew = old_pd.kl(pd)
        ent = pd.entropy()
        meankl = tf.reduce_mean(kloldnew)
        meanent = tf.reduce_mean(ent)
        entbonus = ent_coef * meanent
        ratio = tf.exp(pd.logp(ac) - old_pd.logp(ac))
        surrgain = tf.reduce_mean(ratio * atarg)
        optimgain = surrgain + entbonus
        losses = [optimgain, meankl, entbonus, surrgain, meanent]
        return losses

    #ob shape should be [batch_size, ob_dim], merged nenv
    #ret shape should be [batch_size]
    @tf.function
    def compute_vflossandgrad(ob, ret):
        with tf.GradientTape() as tape:
            pi_vf = pi.value(ob)
            vferr = tf.reduce_mean(tf.square(pi_vf - ret))
        return U.flatgrad(tape.gradient(vferr, vf_var_list), vf_var_list)

    @tf.function
    def compute_fvp(flat_tangent, ob, ac, atarg):
        with tf.GradientTape() as outter_tape:
            with tf.GradientTape() as inner_tape:
                old_policy_latent = oldpi.policy_network(ob)
                old_pd, _ = oldpi.pdtype.pdfromlatent(old_policy_latent)
                policy_latent = pi.policy_network(ob)
                pd, _ = pi.pdtype.pdfromlatent(policy_latent)
                kloldnew = old_pd.kl(pd)
                meankl = tf.reduce_mean(kloldnew)
            klgrads = inner_tape.gradient(meankl, pi_var_list)
            start = 0
            tangents = []
            for shape in shapes:
                sz = U.intprod(shape)
                tangents.append(tf.reshape(flat_tangent[start:start+sz], shape))
                start += sz
            gvp = tf.add_n([tf.reduce_sum(g*tangent) for (g, tangent) in zipsame(klgrads, tangents)])
        hessians_products = outter_tape.gradient(gvp, pi_var_list)
        fvp = U.flatgrad(hessians_products, pi_var_list)
        return fvp

    @contextmanager
    def timed(msg):
        if rank == 0:
            print(colorize(msg, color='magenta'))
            tstart = time.time()
            yield
            print(colorize("done in %.3f seconds"%(time.time() - tstart), color='magenta'))
        else:
            yield

    def allmean(x):
        assert isinstance(x, np.ndarray)
        if MPI is not None:
            out = np.empty_like(x)
            MPI.COMM_WORLD.Allreduce(x, out, op=MPI.SUM)
            out /= nworkers
        else:
            out = np.copy(x)

        return out

    th_init = get_flat()
    if MPI is not None:
        MPI.COMM_WORLD.Bcast(th_init, root=0)

    set_from_flat(th_init)
    vfadam.sync()
    print("Init param sum", th_init.sum(), flush=True)

    # Prepare for rollouts
    # ----------------------------------------
    seg_gen = traj_segment_generator(pi, env, timesteps_per_batch)

    episodes_so_far = 0
    timesteps_so_far = 0
    iters_so_far = 0
    tstart = time.time()
    lenbuffer = deque(maxlen=40) # rolling buffer for episode lengths
    rewbuffer = deque(maxlen=40) # rolling buffer for episode rewards

    # ---------------------- New ----------------------
    rewforbuffer = deque(maxlen=40)
    rewctrlbuffer = deque(maxlen=40)
    rewconbuffer = deque(maxlen=40)
    rewsurbuffer = deque(maxlen=40)

    rewformeanbuf = np.array([])
    rewctrlmeanbuf = np.array([])
    rewconmeanbuf = np.array([])
    rewsurmeanbuf = np.array([])
    # -------------------------------------------------

    if sum([max_iters>0, total_timesteps>0, max_episodes>0])==0:
        # nothing to be done
        return pi

    assert sum([max_iters>0, total_timesteps>0, max_episodes>0]) < 2, \
        'out of max_iters, total_timesteps, and max_episodes only one should be specified'

    x_axis = 0
    x_holder = np.array([])
    rew_holder = np.array([])
    while True:
        if timesteps_so_far > total_timesteps-1500: #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # Set recording XXXX timesteps before ending
            env = VecVideoRecorder (env, osp.join(logger.get_dir(), "videos"), record_video_trigger=lambda x: True, video_length=200)
            seg_gen = traj_segment_generator(pi, env, timesteps_per_batch)
        
        if callback: callback(locals(), globals())
        if total_timesteps and timesteps_so_far >= total_timesteps:
            break
        elif max_episodes and episodes_so_far >= max_episodes:
            break
        elif max_iters and iters_so_far >= max_iters:
            break
        logger.log("********** Iteration %i ************"%iters_so_far)

        with timed("sampling"):
            seg = seg_gen.__next__()

        add_vtarg_and_adv(seg, gamma, lam)

        # ob, ac, atarg, ret, td1ret = map(np.concatenate, (obs, acs, atargs, rets, td1rets))
        ob, ac, atarg, tdlamret = seg["ob"], seg["ac"], seg["adv"], seg["tdlamret"]
        ob = sf01(ob)
        vpredbefore = seg["vpred"] # predicted value function before udpate
        atarg = (atarg - atarg.mean()) / atarg.std() # standardized advantage function estimate

        if hasattr(pi, "ret_rms"): pi.ret_rms.update(tdlamret)
        if hasattr(pi, "ob_rms"): pi.ob_rms.update(ob) # update running mean/std for policy

        args = ob, ac, atarg
        fvpargs = [arr[::5] for arr in args]
        def fisher_vector_product(p):
            return allmean(compute_fvp(p, *fvpargs).numpy()) + cg_damping * p

        assign_old_eq_new() # set old parameter values to new parameter values
        with timed("computegrad"):
            *lossbefore, g = compute_lossandgrad(*args)
        lossbefore = allmean(np.array(lossbefore))
        g = g.numpy()
        g = allmean(g)
        if np.allclose(g, 0):
            logger.log("Got zero gradient. not updating")
        else:
            with timed("cg"):
                stepdir = cg(fisher_vector_product, g, cg_iters=cg_iters, verbose=rank==0)
            assert np.isfinite(stepdir).all()
            shs = .5*stepdir.dot(fisher_vector_product(stepdir))
            lm = np.sqrt(shs / max_kl)
            # logger.log("lagrange multiplier:", lm, "gnorm:", np.linalg.norm(g))
            fullstep = stepdir / lm
            expectedimprove = g.dot(fullstep)
            surrbefore = lossbefore[0]
            stepsize = 1.0
            thbefore = get_flat()
            for _ in range(10):
                thnew = thbefore + fullstep * stepsize
                set_from_flat(thnew)
                meanlosses = surr, kl, *_ = allmean(np.array(compute_losses(*args)))
                improve = surr - surrbefore
                logger.log("Expected: %.3f Actual: %.3f"%(expectedimprove, improve))
                if not np.isfinite(meanlosses).all():
                    logger.log("Got non-finite value of losses -- bad!")
                elif kl > max_kl * 1.5:
                    logger.log("violated KL constraint. shrinking step.")
                elif improve < 0:
                    logger.log("surrogate didn't improve. shrinking step.")
                else:
                    logger.log("Stepsize OK!")
                    break
                stepsize *= .5
            else:
                logger.log("couldn't compute a good step")
                set_from_flat(thbefore)
            if nworkers > 1 and iters_so_far % 20 == 0:
                paramsums = MPI.COMM_WORLD.allgather((thnew.sum(), vfadam.getflat().sum())) # list of tuples
                assert all(np.allclose(ps, paramsums[0]) for ps in paramsums[1:])

        for (lossname, lossval) in zip(loss_names, meanlosses):
            logger.record_tabular(lossname, lossval)

        with timed("vf"):

            for _ in range(vf_iters):
                for (mbob, mbret) in dataset.iterbatches((seg["ob"], seg["tdlamret"]),
                include_final_partial_batch=False, batch_size=64):
                    mbob = sf01(mbob)
                    g = allmean(compute_vflossandgrad(mbob, mbret).numpy())
                    vfadam.update(g, vf_stepsize)

        logger.record_tabular("ev_tdlam_before", explained_variance(vpredbefore, tdlamret))

        lrlocal = (seg["ep_lens"], seg["ep_rets"], seg["ep_rets_for"], seg["ep_rets_ctrl"], seg["ep_rets_con"], seg["ep_rets_sur"]) # local values
        if MPI is not None:
            listoflrpairs = MPI.COMM_WORLD.allgather(lrlocal) # list of tuples
        else:
            listoflrpairs = [lrlocal]

        lens, rews, rews_for, rews_ctrl, rews_con, rews_sur = map(flatten_lists, zip(*listoflrpairs))
        lenbuffer.extend(lens)
        rewbuffer.extend(rews)

        # ---------------------- New ----------------------
        rewforbuffer.extend(rews_for)
        rewctrlbuffer.extend(rews_ctrl)
        rewconbuffer.extend(rews_con)
        rewsurbuffer.extend(rews_sur)

        rewformeanbuf = np.append([rewformeanbuf],[np.mean(rewforbuffer)])
        rewctrlmeanbuf = np.append([rewctrlmeanbuf],[np.mean(rewctrlbuffer)])
        rewconmeanbuf = np.append([rewconmeanbuf],[np.mean(rewconbuffer)])
        rewsurmeanbuf = np.append([rewsurmeanbuf],[np.mean(rewsurbuffer)])
        # -------------------------------------------------

        logger.record_tabular("EpLenMean", np.mean(lenbuffer))
        logger.record_tabular("EpRewMean", np.mean(rewbuffer))
        logger.record_tabular("EpThisIter", len(lens))
        episodes_so_far += len(lens)
        timesteps_so_far += sum(lens)
        iters_so_far += 1

        logger.record_tabular("EpisodesSoFar", episodes_so_far)
        logger.record_tabular("TimestepsSoFar", timesteps_so_far)
        logger.record_tabular("TimeElapsed", time.time() - tstart)

        if rank==0:
            logger.dump_tabular()

        x_axis += 1
        x_holder = np.append([x_holder],[x_axis])
        rew_holder = np.append([rew_holder],[np.mean(rewbuffer)])

    # --------------------------------------- NEW -----------------------------------------------------
    with open("img_rec.txt", "r") as rec:
        cur_gen = rec.read()
        cur_gen = cur_gen.strip() # remove \n

    dir_of_gens = ['1_1','2_1','3_1','1_2','2_2',
               '3_2','1_3','2_3','3_3','1_4',
               '2_4','3_4','1_5','2_5','3_5',
               '1_6','2_6','3_6','1_7','2_7',
               '3_7','1_8','2_8','3_8','1_9',
               '2_9','3_9','1_10','2_10','3_10',
               '1_11','2_11','3_11','1_12','2_12',
               '3_12']
    # -------------------------------------------------------------------------------------------------

    from matplotlib import pyplot as plt
    f = plt.figure(1)
    plt.plot(x_holder,rew_holder)
    plt.title("Rewards for Ant v2")
    plt.grid(True)
    plt.savefig('rewards_for_antv2_{}'.format(cur_gen))

    g = plt.figure(2)
    plt.plot(x_holder,rewformeanbuf, label='Forward Reward')
    plt.plot(x_holder,rewctrlmeanbuf, label='CTRL Cost')
    plt.plot(x_holder,rewconmeanbuf, label='Contact Cost')
    plt.plot(x_holder,rewsurmeanbuf, label='Survive Reward')
    plt.title("Reward Breakdown")
    plt.legend()
    plt.grid(True)
    plt.savefig('rewards_breakdown{}'.format(cur_gen))

    # plt.show()

    # --------------------------------------- NEW -----------------------------------------------------
    elem = int(dir_of_gens.index(cur_gen))
    with open("img_rec.txt","w") as rec:
        if elem == 35:
            new_elem = 0
        else:
            new_elem = elem+1
        new_gen = cur_gen.replace(cur_gen,dir_of_gens[new_elem])
        rec.write(new_gen)
    # -------------------------------------------------------------------------------------------------


    #----------------------------------------------------------- SAVE WEIGHTS ------------------------------------------------------------#        
    # np.save('val_weights_bias_2_c',val_weights_bias_2_c) # <-------------------------------------------------------------------------------------
    # save = save.replace(save[0],'..',2)
    # os.chdir(save)
    # name = 'max_reward'
    # completeName = os.path.join(name+".txt")
    # file1 = open(completeName,"w")
    # toFile = str(np.mean(rewbuffer))
    # file1.write(toFile)
    # file1.close()
    # os.chdir('../../../baselines-tf2')

    return pi

def flatten_lists(listoflists):
    return [el for list_ in listoflists for el in list_]

def sf01(arr):
    """
    swap and then flatten axes 0 and 1
    """
    s = arr.shape
    return arr.swapaxes(0, 1).reshape(s[0] * s[1], *s[2:])
