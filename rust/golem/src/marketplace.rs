pub struct Offer {
    price: f64,
}

impl Offer {
    pub fn new(price: f64) -> Offer {
        Offer { price }
    }
}

pub fn order_providers(offers: &[Offer]) -> Vec<usize> {
    let mut perm: Vec<usize> = (0..offers.len()).collect();
    perm.sort_by(|lhs, rhs| offers[*lhs].price.partial_cmp(&offers[*rhs].price).unwrap());
    perm
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn order_providers_sanity() {
        let offer0 = Offer { price: 2.0 };
        let offer1 = Offer { price: 2.2 };
        let offer2 = Offer { price: 1.7 };
        let offer3 = Offer { price: 4.4 };
        assert_eq!(
            order_providers(&vec![offer0, offer1, offer2, offer3]),
            vec![2, 0, 1, 3]
        );
    }
}
