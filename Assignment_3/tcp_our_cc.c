#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/types.h>
#include <net/tcp.h>

/* Per-connection state for delay-based congestion avoidance. */
struct our_cc {
	u32 min_rtt_us;
	u32 curr_rtt_us;
};

static u32 ssthresh(struct sock *sk)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	u32 reduced = (tp->snd_cwnd * 3U) / 4U;

	return max(reduced, 2U);
}

static void pkts_acked(struct sock *sk, const struct ack_sample *sample)
{
	struct our_cc *ca = inet_csk_ca(sk);
	u32 curr_rtt_us;

	if (!sample || sample->rtt_us <= 0)
		return;

	curr_rtt_us = (u32)sample->rtt_us;
	ca->curr_rtt_us = curr_rtt_us;

	if (ca->min_rtt_us == 0 || curr_rtt_us < ca->min_rtt_us)
		ca->min_rtt_us = curr_rtt_us;
}

static void cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct our_cc *ca = inet_csk_ca(sk);
	u32 cwnd;
	u32 target_rtt_us;
	u32 delta;

	(void)ack;

	if (!acked)
		return;

	if (tp->snd_cwnd < tp->snd_ssthresh) {
		tp->snd_cwnd += acked;
		return;
	}

	if (ca->min_rtt_us == 0) {
		cwnd = max(tp->snd_cwnd, 1U);
		delta = acked / cwnd;
		tp->snd_cwnd += delta;
		return;
	}

	target_rtt_us = (ca->min_rtt_us * 6U) / 5U;
	if (ca->curr_rtt_us < target_rtt_us) {
		cwnd = max(tp->snd_cwnd, 1U);
		delta = acked / cwnd;
		tp->snd_cwnd += delta;
	}
}

static void set_state(struct sock *sk, u8 new_state)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct our_cc *ca = inet_csk_ca(sk);

	if (new_state == TCP_CA_Loss) {
		tp->snd_cwnd = 1U;
		ca->min_rtt_us = 0;
	}
}

static u32 undo_cwnd(struct sock *sk)
{
	const struct tcp_sock *tp = tcp_sk(sk);

	return max(tp->prior_cwnd, tp->snd_cwnd);
}

static void our_cc_init(struct sock *sk)
{
	struct our_cc *ca = inet_csk_ca(sk);

	ca->min_rtt_us = 0;
	ca->curr_rtt_us = 0;
}

static struct tcp_congestion_ops tcp_our_cc __read_mostly = {
	.flags = TCP_CONG_NON_RESTRICTED,
	.name = "our_cc",
	.owner = THIS_MODULE,
	.init = our_cc_init,
	.ssthresh = ssthresh,
	.pkts_acked = pkts_acked,
	.cong_avoid = cong_avoid,
	.set_state = set_state,
	.undo_cwnd = undo_cwnd,
};

static int __init our_cc_register(void)
{
	pr_info("our_cc: registering congestion control\n");
	return tcp_register_congestion_control(&tcp_our_cc);
}

static void __exit our_cc_unregister(void)
{
	pr_info("our_cc: unregistering congestion control\n");
	tcp_unregister_congestion_control(&tcp_our_cc);
}

module_init(our_cc_register);
module_exit(our_cc_unregister);

MODULE_AUTHOR("LeBron James haha no im just kidding");
MODULE_DESCRIPTION("Our congestion control algorithm based on the pseudocode from Assignment 2");
MODULE_LICENSE("GPL");
