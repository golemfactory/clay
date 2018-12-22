// Price sensitivity factor. 0 <= ALPHA <= 1
const ALPHA: f64 = 0.67;
// Distrust factor. 1 <= D
const D: f64 = 5.0;
// History forgetting factor. 0 < PSI < 1
const PSI: f64 = 0.9;

pub struct Quality {
    pub s: f64,
    pub t: f64,
    pub f: f64,
    pub r: f64,
}

pub struct Offer {
    pub scaled_price: f64,
    pub reputation: f64,
    pub quality: Quality,
}

pub fn order_providers(offers: Vec<Offer>) -> Vec<usize> {
    order_providers_impl(offers, ALPHA, PSI, D)
}

fn order_providers_impl(offers: Vec<Offer>, alpha: f64, psi: f64, d: f64) -> Vec<usize> {
    let q_star = (1.0 + 1.0 / (1.0 - psi)) / (d + 1.0 / (1.0 - psi));
    let score = |offer: &Offer| -> f64 {
        let q = (1.0 + offer.quality.s)
            / (d + offer.quality.s + offer.quality.t + offer.quality.f + offer.quality.r)
            / q_star;
        alpha * offer.scaled_price + (1.0 - alpha) * offer.reputation * q
    };
    let mut perm: Vec<(usize, f64)> = (0..offers.len())
        .map(|ind| (ind, score(&offers[ind])))
        .collect();
    perm.sort_by(|lhs, rhs| rhs.1.partial_cmp(&lhs.1).unwrap());
    perm.iter().map(|(ind, _)| *ind).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    fn gen_offers() -> Vec<Offer> {
        return vec![
            Offer {
                scaled_price: 2.0,
                reputation: 10.0,
                quality: Quality {
                    s: 0.0,
                    t: 0.0,
                    f: 0.0,
                    r: 0.0,
                },
            },
            Offer {
                scaled_price: 2.2,
                reputation: 20.0,
                quality: Quality {
                    s: 0.0,
                    t: 0.0,
                    f: 0.0,
                    r: 0.0,
                },
            },
            Offer {
                scaled_price: 1.7,
                reputation: 17.0,
                quality: Quality {
                    s: 0.0,
                    t: 0.0,
                    f: 0.0,
                    r: 0.0,
                },
            },
            Offer {
                scaled_price: 4.4,
                reputation: 14.0,
                quality: Quality {
                    s: 0.0,
                    t: 0.0,
                    f: 0.0,
                    r: 0.0,
                },
            },
        ];
    }
    #[test]
    fn order_providers_price_preference() {
        let offers = gen_offers();
        assert_eq!(order_providers_impl(offers, 1.0, PSI, D), vec![3, 1, 0, 2]);
    }
    #[test]
    fn order_providers_reputation_preference() {
        let offers = gen_offers();
        assert_eq!(order_providers_impl(offers, 0.0, PSI, D), vec![1, 2, 3, 0]);
    }
}
